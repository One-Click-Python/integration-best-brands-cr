#!/usr/bin/env python3
"""
FASE 1: Pre-Testing Validation Script
Automated validation for Order Polling historical sync testing
"""

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
import redis.asyncio as aioredis
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from sqlalchemy import text

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.db.connection import get_db_connection

console = Console()


class Phase1Validator:
    """Phase 1: Pre-Testing Validation"""

    def __init__(self, skip_backup_prompt: bool = False):
        self.results = {}
        self.baseline = {}
        self.redis_client = None
        self.db_conn = None
        self.skip_backup_prompt = skip_backup_prompt

    async def run(self):
        """Execute all Phase 1 validation steps"""
        console.print(
            Panel.fit(
                "[bold cyan]FASE 1: Pre-Testing Validation[/bold cyan]\n"
                "[yellow]Automated validation before Order Polling tests[/yellow]",
                title="🔍 Order Polling Test Suite",
            )
        )

        # Step 1: Manual backup reminder
        await self._reminder_backup()

        # Initialize database connection
        await self._initialize_db()

        # Step 2: Baseline documentation
        await self._baseline_documentation()

        # Step 3: Environment verification
        await self._verify_redis()
        await self._verify_rms_database()
        await self._verify_shopify_api()
        await self._verify_polling_endpoint()

        # Generate report
        await self._generate_report()

        # Save baseline
        await self._save_baseline()

    async def _initialize_db(self):
        """Initialize database connection"""
        try:
            self.db_conn = get_db_connection()
            await self.db_conn.initialize()
        except Exception as e:
            console.print(f"[red]❌ Failed to initialize database: {e!s}[/red]")
            raise

    async def _reminder_backup(self):
        """Remind user about manual backup"""
        console.print("\n[bold yellow]⚠️  STEP 1: Database Backup (MANUAL)[/bold yellow]")

        if self.skip_backup_prompt:
            console.print(
                "[yellow]⚠️  WARNING: Backup prompt skipped (--skip-backup-prompt flag)[/yellow]"
            )
            console.print(
                "[red]CRITICAL:[/red] Ensure you have created a backup before running tests!\n"
            )
            console.print("📄 Backup instructions: [cyan]scripts/phase1_backup_instructions.sql[/cyan]\n")

            self.results["backup"] = {
                "completed": False,
                "skipped": True,
                "location": "N/A - Prompt skipped",
                "timestamp": datetime.now(UTC).isoformat(),
            }
            console.print("[yellow]⚠️  Backup verification skipped[/yellow]")
            return

        console.print(
            "[red]CRITICAL:[/red] You must create a database backup before proceeding!\n"
        )
        console.print("📄 Backup instructions: [cyan]scripts/phase1_backup_instructions.sql[/cyan]")
        console.print("\n[bold]Options:[/bold]")
        console.print("  1. Full database backup (RECOMMENDED)")
        console.print("  2. Order tables backup (faster, limited restore)\n")

        response = input("Have you completed the backup? (yes/no): ").strip().lower()
        if response != "yes":
            console.print("[red]❌ Cannot proceed without backup. Exiting...[/red]")
            sys.exit(1)

        backup_location = input("Enter backup file location (e.g., C:\\Backups\\...): ").strip()
        self.results["backup"] = {
            "completed": True,
            "location": backup_location,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        console.print("[green]✅ Backup confirmed[/green]")

    async def _baseline_documentation(self):
        """Document baseline state of RMS orders"""
        console.print("\n[bold cyan]📊 STEP 2: Baseline Documentation[/bold cyan]")

        try:
            async with self.db_conn.get_session() as session:
                # Count total Shopify orders
                result = await session.execute(
                    text("SELECT COUNT(*) as total FROM [Order] WHERE ChannelType = 2")
                )
                total_orders = result.scalar()

                # Get last order ID
                result = await session.execute(
                    text(
                        "SELECT MAX(ID) as last_id FROM [Order] WHERE ChannelType = 2"
                    )
                )
                last_order_id = result.scalar() or 0

                # Count orders in last 30 days
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*) as recent
                        FROM [Order]
                        WHERE ChannelType = 2
                          AND Time >= DATEADD(DAY, -30, GETDATE())
                        """
                    )
                )
                recent_orders = result.scalar()

                # Count orders in last 7 days
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*) as weekly
                        FROM [Order]
                        WHERE ChannelType = 2
                          AND Time >= DATEADD(DAY, -7, GETDATE())
                        """
                    )
                )
                weekly_orders = result.scalar()

                # Count orders in last 24 hours
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*) as daily
                        FROM [Order]
                        WHERE ChannelType = 2
                          AND Time >= DATEADD(HOUR, -24, GETDATE())
                        """
                    )
                )
                daily_orders = result.scalar()

                # Check for duplicates (should be 0)
                result = await session.execute(
                    text(
                        """
                        SELECT COUNT(*) as duplicates
                        FROM (
                            SELECT ReferenceNumber, COUNT(*) as cnt
                            FROM [Order]
                            WHERE ChannelType = 2
                            GROUP BY ReferenceNumber
                            HAVING COUNT(*) > 1
                        ) as dups
                        """
                    )
                )
                duplicates = result.scalar()

                self.baseline = {
                    "total_orders": total_orders,
                    "last_order_id": last_order_id,
                    "orders_last_30_days": recent_orders,
                    "orders_last_7_days": weekly_orders,
                    "orders_last_24_hours": daily_orders,
                    "duplicates_detected": duplicates,
                    "timestamp": datetime.now(UTC).isoformat(),
                }

                # Display baseline
                table = Table(title="RMS Order Baseline")
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")

                table.add_row("Total Shopify Orders", str(total_orders))
                table.add_row("Last Order ID", str(last_order_id))
                table.add_row("Orders (Last 30 Days)", str(recent_orders))
                table.add_row("Orders (Last 7 Days)", str(weekly_orders))
                table.add_row("Orders (Last 24 Hours)", str(daily_orders))
                table.add_row(
                    "Duplicates Detected",
                    f"[red]{duplicates}[/red]" if duplicates > 0 else "[green]0[/green]",
                )

                console.print(table)

                self.results["baseline"] = {"success": True, "data": self.baseline}

                if duplicates > 0:
                    console.print(
                        f"[red]⚠️  WARNING: {duplicates} duplicate ReferenceNumbers detected![/red]"
                    )

                console.print("[green]✅ Baseline documented[/green]")

        except Exception as e:
            console.print(f"[red]❌ Baseline documentation failed: {e!s}[/red]")
            self.results["baseline"] = {"success": False, "error": str(e)}
            raise

    async def _verify_redis(self):
        """Verify Redis connectivity"""
        console.print("\n[bold cyan]🔗 STEP 3a: Redis Connectivity[/bold cyan]")

        try:
            self.redis_client = aioredis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
            await self.redis_client.ping()

            # Check if order polling stats exist
            stats_key = "order_polling:statistics"
            stats_exists = await self.redis_client.exists(stats_key)

            if stats_exists:
                stats = await self.redis_client.hgetall(stats_key)
                console.print(f"[green]✅ Redis connected. Existing stats found: {stats}[/green]")
            else:
                console.print("[green]✅ Redis connected. No existing polling stats.[/green]")

            self.results["redis"] = {"success": True, "stats_exist": bool(stats_exists)}

        except Exception as e:
            console.print(f"[red]❌ Redis connection failed: {e!s}[/red]")
            self.results["redis"] = {"success": False, "error": str(e)}
            raise

    async def _verify_rms_database(self):
        """Verify RMS database connectivity"""
        console.print("\n[bold cyan]🗄️  STEP 3b: RMS Database Access[/bold cyan]")

        try:
            async with self.db_conn.get_session() as session:
                result = await session.execute(text("SELECT @@VERSION"))
                version = result.scalar()
                console.print("[green]✅ RMS database connected[/green]")
                console.print(f"[dim]{version[:80]}...[/dim]")

            self.results["rms_database"] = {"success": True}

        except Exception as e:
            console.print(f"[red]❌ RMS database connection failed: {e!s}[/red]")
            self.results["rms_database"] = {"success": False, "error": str(e)}
            raise

    async def _verify_shopify_api(self):
        """Verify Shopify GraphQL API access"""
        console.print("\n[bold cyan]🛍️  STEP 3c: Shopify GraphQL API[/bold cyan]")

        try:
            async with httpx.AsyncClient() as client:
                query = """
                {
                  shop {
                    name
                    email
                    currencyCode
                  }
                }
                """

                response = await client.post(
                    f"https://{settings.SHOPIFY_SHOP_URL}/admin/api/{settings.SHOPIFY_API_VERSION}/graphql.json",
                    json={"query": query},
                    headers={
                        "X-Shopify-Access-Token": settings.SHOPIFY_ACCESS_TOKEN,
                        "Content-Type": "application/json",
                    },
                    timeout=30.0,
                )

                response.raise_for_status()
                data = response.json()

                if "errors" in data:
                    raise ValueError(f"GraphQL errors: {data['errors']}")

                shop_info = data["data"]["shop"]
                console.print("[green]✅ Shopify API connected[/green]")
                console.print(f"[dim]Shop: {shop_info['name']} ({shop_info['email']})[/dim]")

                self.results["shopify_api"] = {"success": True, "shop": shop_info}

        except Exception as e:
            console.print(f"[red]❌ Shopify API access failed: {e!s}[/red]")
            self.results["shopify_api"] = {"success": False, "error": str(e)}
            raise

    async def _verify_polling_endpoint(self):
        """Verify order polling status endpoint"""
        console.print("\n[bold cyan]📡 STEP 3d: Order Polling Endpoint[/bold cyan]")

        try:
            # Assuming app is running on localhost:8080
            base_url = "http://localhost:8080"

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{base_url}/api/v1/orders/polling/status", timeout=10.0
                )
                response.raise_for_status()
                status_data = response.json()

                console.print("[green]✅ Order polling endpoint accessible[/green]")

                # Display key info
                data = status_data.get("data", {})
                console.print(f"[dim]Enabled: {data.get('enabled')}[/dim]")
                console.print(f"[dim]Interval: {data.get('interval_minutes')} minutes[/dim]")
                console.print(f"[dim]Lookback: {data.get('lookback_minutes')} minutes[/dim]")

                self.results["polling_endpoint"] = {"success": True, "status": data}

        except httpx.ConnectError:
            console.print(
                "[yellow]⚠️  Cannot connect to app. Is it running on localhost:8080?[/yellow]"
            )
            self.results["polling_endpoint"] = {
                "success": False,
                "error": "App not running",
            }
        except Exception as e:
            console.print(f"[red]❌ Polling endpoint check failed: {e!s}[/red]")
            self.results["polling_endpoint"] = {"success": False, "error": str(e)}

    async def _generate_report(self):
        """Generate validation report"""
        console.print("\n" + "=" * 80)
        console.print("[bold cyan]📋 PHASE 1 VALIDATION REPORT[/bold cyan]")
        console.print("=" * 80)

        # Summary table
        table = Table(title="Validation Summary")
        table.add_column("Component", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Details", style="dim")

        for component, result in self.results.items():
            status = "[green]✅ PASS[/green]" if result.get("success", False) else "[red]❌ FAIL[/red]"
            details = result.get("error", "OK") if not result.get("success", False) else "OK"
            table.add_row(component.replace("_", " ").title(), status, details)

        console.print(table)

        # Overall result
        all_passed = all(r.get("success", False) for r in self.results.values() if r)
        if all_passed:
            console.print(
                "\n[bold green]✅ ALL CHECKS PASSED - Ready for Phase 2[/bold green]"
            )
        else:
            console.print(
                "\n[bold red]❌ SOME CHECKS FAILED - Fix issues before proceeding[/bold red]"
            )

    async def _save_baseline(self):
        """Save baseline to file"""
        baseline_file = Path("baseline_order_polling_test.json")

        baseline_data = {
            "phase": "Phase 1: Pre-Testing Validation",
            "timestamp": datetime.now(UTC).isoformat(),
            "baseline": self.baseline,
            "validation_results": self.results,
        }

        baseline_file.write_text(json.dumps(baseline_data, indent=2))
        console.print(f"\n[green]💾 Baseline saved to: {baseline_file}[/green]")

    async def cleanup(self):
        """Cleanup resources"""
        if self.redis_client:
            await self.redis_client.aclose()
        if self.db_conn:
            await self.db_conn.close()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Phase 1: Pre-Testing Validation for Order Polling"
    )
    parser.add_argument(
        "--skip-backup-prompt",
        action="store_true",
        help="Skip interactive backup prompt (WARNING: Ensure backup is done manually!)",
    )

    args = parser.parse_args()

    validator = Phase1Validator(skip_backup_prompt=args.skip_backup_prompt)
    try:
        await validator.run()
    except Exception as e:
        console.print(f"\n[red]❌ Validation failed: {e!s}[/red]")
        sys.exit(1)
    finally:
        await validator.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
