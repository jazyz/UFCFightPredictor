#!/usr/bin/env python3
"""
Test script for incremental scraping and processing
Run this to validate your setup without training the model
"""

import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scrapers.scrape_incremental import get_last_scraped_date, get_new_events
from utils.incremental_processing import get_last_processed_date, needs_full_reprocess


def test_data_state():
    """Check current state of data files"""
    print("\n" + "="*60)
    print("TESTING DATA STATE")
    print("="*60 + "\n")
    
    # Check raw data
    raw_path = 'data/fight_details_date.csv'
    if os.path.exists(raw_path):
        import pandas as pd
        df = pd.read_csv(raw_path)
        last_scraped = get_last_scraped_date()
        print(f"✓ Raw data exists: {len(df)} fights")
        print(f"  Last scraped date: {last_scraped.strftime('%B %d, %Y') if last_scraped else 'N/A'}")
    else:
        print("✗ No raw data found - you need to scrape first")
        return False
    
    # Check processed data
    processed_path = 'data/modified_fight_details.csv'
    if os.path.exists(processed_path):
        df = pd.read_csv(processed_path)
        last_processed = get_last_processed_date()
        print(f"✓ Processed data exists: {len(df)} fights")
        print(f"  Last processed date: {last_processed.strftime('%Y-%m-%d') if last_processed else 'N/A'}")
    else:
        print("⚠ No processed data found")
    
    # Check feature-engineered data
    detailed_path = 'data/detailed_fights.csv'
    if os.path.exists(detailed_path):
        df = pd.read_csv(detailed_path)
        print(f"✓ Feature data exists: {len(df)} fights")
        needs_reprocess = needs_full_reprocess()
        print(f"  Needs reprocessing: {'Yes' if needs_reprocess else 'No'}")
    else:
        print("⚠ No feature-engineered data found")
    
    return True


def test_new_events_check():
    """Check if there are new events to scrape"""
    print("\n" + "="*60)
    print("CHECKING FOR NEW EVENTS")
    print("="*60 + "\n")
    
    try:
        last_date = get_last_scraped_date()
        print(f"Checking UFC stats for events after: {last_date.strftime('%B %d, %Y') if last_date else 'beginning'}")
        print("(This may take a moment...)\n")
        
        new_events = get_new_events(last_date)
        
        if new_events:
            print(f"✓ Found {len(new_events)} new events:")
            for event_url, details in new_events.items():
                print(f"  • {details['date']}: {len(details['links'])} fights")
        else:
            print("✓ No new events found - your data is up to date!")
        
        return True
        
    except Exception as e:
        print(f"✗ Error checking for new events: {e}")
        return False


def test_directories():
    """Check if required directories exist"""
    print("\n" + "="*60)
    print("CHECKING DIRECTORY STRUCTURE")
    print("="*60 + "\n")
    
    required_dirs = ['data', 'scrapers', 'utils', 'saved_models']
    all_exist = True
    
    for dir_name in required_dirs:
        if os.path.exists(dir_name):
            print(f"✓ {dir_name}/")
        else:
            print(f"✗ {dir_name}/ - missing!")
            all_exist = False
    
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')
        print("✓ logs/ (created)")
    else:
        print("✓ logs/")
    
    return all_exist


def test_dependencies():
    """Check if required Python packages are installed"""
    print("\n" + "="*60)
    print("CHECKING PYTHON DEPENDENCIES")
    print("="*60 + "\n")
    
    required_packages = [
        'requests',
        'beautifulsoup4',
        'pandas',
        'lightgbm',
        'sklearn',
        'numpy'
    ]
    
    all_installed = True
    
    for package in required_packages:
        try:
            if package == 'beautifulsoup4':
                __import__('bs4')
            elif package == 'sklearn':
                __import__('sklearn')
            else:
                __import__(package)
            print(f"✓ {package}")
        except ImportError:
            print(f"✗ {package} - not installed!")
            all_installed = False
    
    if not all_installed:
        print("\nInstall missing packages:")
        print("  pip install -r requirements.txt")
    
    return all_installed


def main():
    """Run all tests"""
    print("\n" + "╔" + "="*58 + "╗")
    print("║" + " "*12 + "UFC FIGHT PREDICTOR SETUP TEST" + " "*16 + "║")
    print("╚" + "="*58 + "╝")
    
    results = []
    
    # Test 1: Dependencies
    results.append(("Dependencies", test_dependencies()))
    
    # Test 2: Directory structure
    results.append(("Directories", test_directories()))
    
    # Test 3: Data state
    results.append(("Data State", test_data_state()))
    
    # Test 4: New events check
    results.append(("New Events", test_new_events_check()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60 + "\n")
    
    all_passed = True
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:8} - {test_name}")
        if not passed:
            all_passed = False
    
    print("\n" + "="*60 + "\n")
    
    if all_passed:
        print("🎉 All tests passed! You're ready to run auto-retraining.")
        print("\nNext steps:")
        print("  1. Test a manual run:")
        print("     python auto_retrain.py --skip-training")
        print("\n  2. Set up automatic scheduling:")
        print("     ./setup_cron.sh")
    else:
        print("⚠️  Some tests failed. Please fix the issues above.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
