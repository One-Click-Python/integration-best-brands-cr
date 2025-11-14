#!/usr/bin/env python3
"""
Investigate duplicate orders in RMS database
"""

import asyncio
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.connection import get_db_connection

console = Console()


async def investigate_duplicates():
    """Find and display duplicate orders"""
    console.print("\n[bold cyan]🔍 Investigating Duplicate Orders[/bold cyan]\n")

    db_conn = get_db_connection()
    await db_conn.initialize()

    try:
        async with db_conn.get_session() as session:
            # Find duplicates
            result = await session.execute(
                text(
                    """
                    SELECT ReferenceNumber, COUNT(*) as cantidad,
                           MIN(ID) as primer_id, MAX(ID) as ultimo_id,
                           MIN(Time) as primera_fecha, MAX(Time) as ultima_fecha
                    FROM [Order]
                    WHERE ChannelType = 2
                    GROUP BY ReferenceNumber
                    HAVING COUNT(*) > 1
                    """
                )
            )

            duplicates = result.fetchall()

            if not duplicates:
                console.print("[green]✅ No duplicates found![/green]")
                return

            # Display duplicates
            table = Table(title="Duplicate Orders Found")
            table.add_column("ReferenceNumber", style="cyan")
            table.add_column("Count", style="yellow")
            table.add_column("First ID", style="dim")
            table.add_column("Last ID", style="dim")
            table.add_column("First Date", style="dim")
            table.add_column("Last Date", style="dim")

            for dup in duplicates:
                table.add_row(
                    str(dup[0]),
                    str(dup[1]),
                    str(dup[2]),
                    str(dup[3]),
                    str(dup[4]),
                    str(dup[5]),
                )

            console.print(table)

            # Get detailed info for each duplicate
            console.print("\n[bold]Detailed Information:[/bold]\n")

            for dup in duplicates:
                ref_number = dup[0]
                console.print(f"[cyan]═══ {ref_number} ═══[/cyan]")

                # Get full details
                result = await session.execute(
                    text(
                        """
                        SELECT o.ID, o.ReferenceNumber, o.Time, o.Total, o.StoreID,
                               o.Comment, o.TransactionNumber, o.BatchNumber,
                               COUNT(oe.ID) as line_items
                        FROM [Order] o
                        LEFT JOIN OrderEntry oe ON o.ID = oe.OrderID
                        WHERE o.ReferenceNumber = :ref
                          AND o.ChannelType = 2
                        GROUP BY o.ID, o.ReferenceNumber, o.Time, o.Total, o.StoreID,
                                 o.Comment, o.TransactionNumber, o.BatchNumber
                        ORDER BY o.ID
                        """
                    ),
                    {"ref": ref_number},
                )

                orders = result.fetchall()

                detail_table = Table()
                detail_table.add_column("ID", style="cyan")
                detail_table.add_column("Time", style="dim")
                detail_table.add_column("Total", style="green")
                detail_table.add_column("Line Items", style="yellow")
                detail_table.add_column("TransactionNumber", style="dim")

                for order in orders:
                    detail_table.add_row(
                        str(order[0]),
                        str(order[2]),
                        f"${order[3]:.2f}" if order[3] else "N/A",
                        str(order[8]),
                        str(order[6]) if order[6] else "N/A",
                    )

                console.print(detail_table)
                console.print()

            # Recommendations
            console.print("\n[bold yellow]📋 Recommendations:[/bold yellow]\n")
            console.print(
                "1. [cyan]Keep the most recent order[/cyan] (highest ID, latest Time)"
            )
            console.print(
                "2. [cyan]Verify line items match[/cyan] before deleting duplicates"
            )
            console.print("3. [cyan]Create backup[/cyan] before any deletion")
            console.print(
                "\n[bold red]⚠️  DO NOT DELETE until backup is confirmed![/bold red]\n"
            )

    finally:
        await db_conn.close()


if __name__ == "__main__":
    asyncio.run(investigate_duplicates())
