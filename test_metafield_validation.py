#!/usr/bin/env python3
"""
Test script to validate that metafields with whitespace-only values are handled correctly.
"""

import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from app.services.data_mapper import RMSToShopifyMapper
from app.api.v1.schemas.rms_schemas import RMSViewItem
from decimal import Decimal


def test_metafield_validation():
    """Test the metafield value validation function."""
    print("Testing metafield value validation...")
    
    # Test cases
    test_cases = [
        (None, False, "None value"),
        ("", False, "Empty string"),
        ("  ", False, "Only spaces"),
        ("\t\n", False, "Only whitespace characters"),
        ("  \n  \t  ", False, "Mixed whitespace"),
        ("ValidValue", True, "Valid string"),
        ("  ValidValue  ", True, "Valid string with surrounding spaces"),
        (123, True, "Integer value"),
        (0, False, "Zero integer"),  # Will be converted to "0" string which is truthy
    ]
    
    for value, expected, description in test_cases:
        result = RMSToShopifyMapper._is_valid_metafield_value(value)
        status = "✅" if result == expected else "❌"
        print(f"{status} {description}: value={repr(value)}, expected={expected}, got={result}")
        
    print("\n" + "="*60 + "\n")


def test_metafield_generation():
    """Test metafield generation with various RMS items."""
    print("Testing metafield generation with whitespace values...")
    
    # Create test RMS item with whitespace-only values
    test_item = RMSViewItem(
        familia="Zapatos",
        genero="Hombre",
        categoria="Tenis",
        ccod="TEST001",
        c_articulo="TEST001-01",
        item_id=12345,
        description="Test Product",
        color="  ",  # Whitespace only - should be filtered
        talla="   ",  # Whitespace only - should be filtered
        quantity=10,
        price=Decimal("100.00"),
        sale_price=None,
        extended_category="  \n  ",  # Whitespace only - should be filtered
        tax=13,
        sale_start_date=None,
        sale_end_date=None
    )
    
    # Generate metafields
    metafields = RMSToShopifyMapper._generate_complete_metafields(test_item)
    
    print(f"Generated {len(metafields)} metafields:\n")
    
    # Check that whitespace-only fields are not included
    for metafield in metafields:
        print(f"  - {metafield['namespace']}:{metafield['key']} = '{metafield['value']}' (type: {metafield['type']})")
    
    # Verify whitespace-only fields were filtered out
    print("\n" + "="*60)
    print("Validation checks:")
    
    # Check that color (whitespace only) is not in metafields
    color_fields = [m for m in metafields if m['key'] == 'color']
    if not color_fields:
        print("✅ Whitespace-only 'color' was correctly filtered out")
    else:
        print(f"❌ Whitespace-only 'color' was NOT filtered: {color_fields}")
    
    # Check that talla (whitespace only) is not in metafields
    talla_fields = [m for m in metafields if m['key'] in ['talla', 'shoe_size', 'clothing_size', 'size']]
    if not talla_fields:
        print("✅ Whitespace-only 'talla' was correctly filtered out")
    else:
        print(f"❌ Whitespace-only 'talla' was NOT filtered: {talla_fields}")
    
    # Check that extended_category (whitespace only) is not in metafields
    extended_cat_fields = [m for m in metafields if m['key'] == 'extended_category']
    if not extended_cat_fields:
        print("✅ Whitespace-only 'extended_category' was correctly filtered out")
    else:
        print(f"❌ Whitespace-only 'extended_category' was NOT filtered: {extended_cat_fields}")
    
    # Check that valid fields are present
    valid_fields = ['familia', 'categoria', 'ccod', 'item_id', 'target_gender', 'age_group']
    for field in valid_fields:
        field_exists = any(m['key'] == field for m in metafields)
        if field_exists:
            print(f"✅ Valid field '{field}' is present")
        else:
            print(f"⚠️  Valid field '{field}' is missing (might be expected)")
    
    print("\n" + "="*60 + "\n")


def test_variant_options_with_whitespace():
    """Test variant options generation with whitespace values."""
    print("Testing variant options with whitespace values...")
    
    from app.services.variant_mapper import VariantMapper
    
    # Create test items with whitespace colors/sizes
    test_items = [
        RMSViewItem(
            familia="Zapatos", genero="Hombre", categoria="Tenis",
            ccod="TEST002", c_articulo="TEST002-01", item_id=1,
            description="Test Product", 
            color="Red",  # Valid color
            talla="42",  # Valid size
            quantity=5, price=Decimal("100.00"), sale_price=None,
            extended_category="", tax=13, sale_start_date=None, sale_end_date=None
        ),
        RMSViewItem(
            familia="Zapatos", genero="Hombre", categoria="Tenis",
            ccod="TEST002", c_articulo="TEST002-02", item_id=2,
            description="Test Product",
            color="  ",  # Whitespace only
            talla="43",  # Valid size
            quantity=3, price=Decimal("100.00"), sale_price=None,
            extended_category="", tax=13, sale_start_date=None, sale_end_date=None
        ),
        RMSViewItem(
            familia="Zapatos", genero="Hombre", categoria="Tenis",
            ccod="TEST002", c_articulo="TEST002-03", item_id=3,
            description="Test Product",
            color="Blue",  # Valid color
            talla="   ",  # Whitespace only
            quantity=0, price=Decimal("100.00"), sale_price=None,
            extended_category="", tax=13, sale_start_date=None, sale_end_date=None
        ),
    ]
    
    # Generate product options
    options = VariantMapper._generate_product_options(test_items)
    
    print(f"Generated {len(options)} options:\n")
    for option in options:
        print(f"  - {option.name}: {option.values}")
    
    print("\n" + "="*60)
    print("Validation checks:")
    
    # Check Color option
    color_option = next((opt for opt in options if opt.name == "Color"), None)
    if color_option:
        # Should only have "Red" and "Blue", not whitespace
        if set(color_option.values) == {"Red", "Blue"}:
            print("✅ Color options correctly filtered whitespace-only values")
        else:
            print(f"❌ Color options contain unexpected values: {color_option.values}")
    
    # Check Size option  
    size_option = next((opt for opt in options if opt.name == "Size"), None)
    if size_option:
        # Should only have "42" and "43", not whitespace
        if set(size_option.values) == {"42", "43"}:
            print("✅ Size options correctly filtered whitespace-only values")
        else:
            print(f"❌ Size options contain unexpected values: {size_option.values}")
    
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    print("="*60)
    print("METAFIELD WHITESPACE VALIDATION TESTS")
    print("="*60 + "\n")
    
    try:
        test_metafield_validation()
        test_metafield_generation()
        test_variant_options_with_whitespace()
        
        print("="*60)
        print("ALL TESTS COMPLETED")
        print("="*60)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)