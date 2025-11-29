#!/usr/bin/env python3
"""Test script for extract_sec_sections tool.

This script tests the extract_sec_sections functionality which extracts
key sections from SEC HTML filing files, significantly reducing token usage.
"""

import json
import os
from pathlib import Path
from tools.sec_tools import SECTools


def test_extract_sec_sections():
    """Test the extract_sec_sections method."""
    print("=" * 70)
    print("Testing extract_sec_sections tool")
    print("=" * 70)

    # Set minimal SEC contact (required for initialization but not used for extraction)
    if not os.getenv("SEC_CONTACT") and not os.getenv("SEC_USER_AGENT"):
        os.environ["SEC_CONTACT"] = "test@example.com"

    # Initialize SEC tools
    sec_tools = SECTools()

    # Test file path
    test_file = Path(
        "files/CRCL/filings/2025-09-30_10-Q_000187604225000047/crcl-20250930.htm"
    )

    if not test_file.exists():
        print(f"❌ Test file not found: {test_file}")
        return

    print(f"\n📄 Test file: {test_file}")
    print(f"📊 File size: {test_file.stat().st_size / 1024 / 1024:.2f} MB")

    # Test 1: Extract default sections (Item 1, Item 1A, Item 7)
    print("\n" + "-" * 70)
    print("Test 1: Extract default sections (Item 1, Item 1A, Item 7)")
    print("-" * 70)

    result1 = sec_tools.extract_sec_sections(str(test_file))

    if "error" in result1:
        print(f"❌ Error: {result1['error']}")
    else:
        print(f"✅ Successfully extracted sections")
        print(f"\nExtracted sections: {list(result1.get('sections', {}).keys())}")

        for section_name, section_text in result1.get("sections", {}).items():
            if section_text.startswith("[Section"):
                print(f"  ⚠️  {section_name}: {section_text}")
            else:
                text_length = len(section_text)
                print(f"\n  ✅ {section_name}: {text_length:,} characters")
                print(f"  {'='*60}")
                print(f"  First 500 characters:")
                print(f"  {section_text[:500]}...")
                print(f"  {'='*60}")

    # Test 2: Extract specific sections
    print("\n" + "-" * 70)
    print("Test 2: Extract specific sections (Item 1 only)")
    print("-" * 70)

    result2 = sec_tools.extract_sec_sections(str(test_file), sections=["Item 1"])

    if "error" in result2:
        print(f"❌ Error: {result2['error']}")
    else:
        print(f"✅ Successfully extracted Item 1")
        item1_text = result2.get("sections", {}).get("Item 1", "")
        if item1_text and not item1_text.startswith("[Section"):
            print(f"  📝 Item 1 length: {len(item1_text):,} characters")
            print(f"  📄 Preview (first 500 chars):\n{item1_text[:500]}")

    # Test 3: Calculate token savings
    print("\n" + "-" * 70)
    print("Test 3: Token savings calculation")
    print("-" * 70)

    full_file_size = test_file.stat().st_size
    full_file_chars = full_file_size  # Approximate: 1 byte ≈ 1 char for UTF-8

    total_extracted = sum(
        len(text)
        for text in result1.get("sections", {}).values()
        if not text.startswith("[Section")
    )

    if total_extracted > 0:
        reduction = (1 - total_extracted / full_file_chars) * 100
        print(f"📊 Full file size: {full_file_chars:,} characters")
        print(f"📊 Extracted sections: {total_extracted:,} characters")
        print(f"💰 Token reduction: {reduction:.1f}%")
        print(
            f"💡 Estimated token savings: ~{int(full_file_chars / 4 * reduction / 100):,} tokens"
        )

    print("\n" + "=" * 70)
    print("Test completed!")
    print("=" * 70)

    # Save extracted content to files
    print("\n" + "-" * 70)
    print("Saving extracted content to files...")
    print("-" * 70)

    output_dir = Path("files/CRCL/notes/extracted_sections")
    output_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for section_name, section_text in result1.get("sections", {}).items():
        if not section_text.startswith("[Section"):
            # Create safe filename
            safe_name = section_name.replace(" ", "_").replace("/", "_")
            output_file = output_dir / f"{safe_name}.txt"
            output_file.write_text(section_text, encoding="utf-8")
            saved_files.append(output_file)
            print(f"✅ Saved {section_name} to: {output_file}")

    if saved_files:
        print(f"\n📁 All extracted sections saved to: {output_dir}")
        print(f"📄 Files saved: {len(saved_files)}")
    else:
        print("⚠️  No content to save")


if __name__ == "__main__":
    test_extract_sec_sections()
