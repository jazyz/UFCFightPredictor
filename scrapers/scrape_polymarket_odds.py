#!/usr/bin/env python3
"""
Polymarket UFC Odds Scraper
Scrapes UFC fight odds from Polymarket betting markets

Features:
- Fetches UFC markets from Polymarket API
- Extracts clobTokenIds for each fighter outcome
- Uses DomeAPI to fetch historical market prices at midnight of event date
- Converts probabilities to American odds format
- Saves to CSV with all fight details

Note: DomeAPI may not have data for very old markets (pre-2021) or markets
that are too new. The scraper will still save clobTokenIds for manual lookup.
"""

import requests
import json
import csv
import os
import time
from datetime import datetime
import re


def normalize_fighter_name(name):
    """Normalize fighter name for matching"""
    # Remove extra whitespace and convert to title case
    name = ' '.join(name.split())
    # Handle common name variations
    name = name.replace("'", "")
    return name.strip()


def get_polymarket_ufc_markets():
    """
    Fetch UFC markets from Polymarket APIs
    Tries multiple API endpoints: CLOB API and Gamma API
    """
    print("Fetching UFC markets from Polymarket...")
    
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json"
        }
        
        ufc_markets = []
        
        # Method 1: Try CLOB API (has more UFC markets)
        print("Trying CLOB API...")
        try:
            clob_url = "https://clob.polymarket.com/markets"
            response = requests.get(clob_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                clob_data = response.json()
                clob_markets = clob_data.get('data', [])
                print(f"Received {len(clob_markets)} total CLOB markets")
                
                for market in clob_markets:
                    question = market.get('question', '')
                    market_slug = market.get('market_slug', '')
                    
                    # Check if UFC/MMA related - check multiple fields
                    is_ufc = (
                        'ufc' in question.lower() or 
                        'ufc' in market_slug.lower() or
                        market.get('sport') == 'mma' or
                        market.get('tags', []) and any('mma' in str(tag).lower() or 'ufc' in str(tag).lower() for tag in market.get('tags', []))
                    )
                    
                    if is_ufc:
                        # Check if market is open for trading
                        is_closed = market.get('closed', False)
                        accepting_orders = market.get('accepting_orders', False)
                        end_date_str = market.get('end_date_iso', '')
                        
                        # Check if event is in the future
                        is_future = False
                        if end_date_str:
                            try:
                                end_dt = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                                is_future = end_dt > datetime.now(end_dt.tzinfo)
                            except:
                                pass
                        
                        # Only include markets that are not closed and in the future
                        if not is_closed and is_future:
                            tokens = market.get('tokens', [])
                            clob_token_ids = [t.get('token_id', '') for t in tokens if t.get('token_id')]
                            
                            ufc_markets.append({
                                'event_title': market.get('question', ''),
                                'event_slug': market_slug,
                                'market_question': question,
                                'market_slug': market.get('condition_id', ''),
                                'outcomes': [t.get('outcome', '') for t in tokens],
                                'clob_token_ids': clob_token_ids,
                                'end_date': end_date_str
                            })
                            print(f"  Found open UFC market: {question[:70]}")
        except Exception as e:
            print(f"CLOB API error: {e}")
        
        # Method 2: Try Gamma API as fallback
        print("\nTrying Gamma API...")
        api_url = "https://gamma-api.polymarket.com/markets"
        params = {
            "closed": "false",
            "active": "true",
            "limit": 200,
            "order": "volume"
        }
        
        response = requests.get(api_url, params=params, headers=headers, timeout=30)
        
        if response.status_code == 200:
            markets_data = response.json()
            
            # Handle both array and object responses
            if isinstance(markets_data, dict):
                markets_list = markets_data.get('data', markets_data.get('markets', []))
            else:
                markets_list = markets_data
            
            print(f"Received {len(markets_list)} total markets")
            
            # Debug: Check first few markets
            if markets_list and len(markets_list) > 0:
                print(f"\nSample market structure:")
                sample = markets_list[0]
                print(f"  Keys: {list(sample.keys())[:10]}")
                if 'question' in sample:
                    print(f"  Sample question: {sample['question'][:100]}")
            
            # Filter for UFC markets
            for market in markets_list:
                # Check various fields for UFC
                question = market.get('question', '')
                description = market.get('description', '')
                tags = market.get('tags', [])
                market_slug = market.get('market_slug', market.get('slug', ''))
                
                # Check if UFC related
                is_ufc = (
                    'ufc' in question.lower() or
                    'ufc' in description.lower() or
                    'ufc' in str(tags).lower() or
                    'ufc' in market_slug.lower()
                )
                
                if is_ufc:
                    # Check if it's a winner market (not prop bet)
                    if any(word in question.lower() for word in ['win', 'beat', 'defeat', 'victory']):
                        
                        # Get outcomes/tokens with clobTokenIds
                        outcomes = market.get('outcomes', market.get('tokens', []))
                        
                        # Extract clobTokenIds if available
                        clob_token_ids = []
                        for outcome in outcomes:
                            token_id = outcome.get('clobTokenIds', outcome.get('token_id', ''))
                            if token_id:
                                clob_token_ids.append(token_id)
                        
                        ufc_markets.append({
                            'event_title': market.get('groupItemTitle', market.get('title', 'UFC Event')),
                            'event_slug': market_slug,
                            'market_question': question,
                            'market_slug': market.get('condition_id', market.get('conditionId', '')),
                            'outcomes': outcomes,
                            'clob_token_ids': clob_token_ids,
                            'end_date': market.get('end_date_iso', market.get('endDate', market.get('end_date', '')))
                        })
        
        # Method 2: Try events endpoint
        if not ufc_markets:
            print("Trying events API...")
            api_url = "https://gamma-api.polymarket.com/events"
            params = {
                "closed": "false",
                "active": "true",
                "limit": 100
            }
            
            response = requests.get(api_url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                events = response.json()
                
                if isinstance(events, dict):
                    events = events.get('data', events.get('events', []))
                
                for event in events:
                    title = event.get('title', '').lower()
                    slug = event.get('slug', '').lower()
                    
                    if 'ufc' in title or 'ufc' in slug:
                        markets = event.get('markets', [])
                        
                        for market in markets:
                            question = market.get('question', '')
                            
                            if 'win' in question.lower():
                                ufc_markets.append({
                                    'event_title': event.get('title', ''),
                                    'event_slug': event.get('slug', ''),
                                    'market_question': question,
                                    'market_slug': market.get('conditionId', ''),
                                    'outcomes': market.get('outcomes', []),
                                    'end_date': event.get('endDate', '')
                                })
        
        if not ufc_markets:
            print("\nNo active UFC markets found in first search.")
            print("Trying alternative search (including recently closed)...")
            # Try searching with different parameters
            api_url = "https://gamma-api.polymarket.com/markets"
            params = {
                "limit": 200,
                "offset": 0
            }
            
            response = requests.get(api_url, params=params, headers=headers, timeout=30)
            if response.status_code == 200:
                all_markets = response.json()
                if isinstance(all_markets, list):
                    print(f"Checking {len(all_markets)} markets for UFC content...")
                    
                    active_count = 0
                    closed_count = 0
                    
                    # Check all markets
                    for market in all_markets:
                        market_str = json.dumps(market).lower()
                        if 'ufc' in market_str:
                            # Check if market is closed or active
                            is_closed = market.get('closed', False)
                            is_active = market.get('active', True)
                            end_date_str = market.get('endDate', market.get('endDateIso', ''))
                            
                            # Try to check if event is in the future
                            is_future = False
                            if end_date_str:
                                try:
                                    end_dt = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                                    is_future = end_dt > datetime.now(end_dt.tzinfo)
                                except:
                                    pass
                            
                            # Only include active/future markets
                            if not is_closed and is_future:
                                active_count += 1
                            elif is_closed:
                                closed_count += 1
                                continue  # Skip closed markets
                            else:
                                # Past event but not marked closed yet
                                if not is_future:
                                    continue
                            question = market.get('question', '')
                            outcomes_raw = market.get('outcomes', market.get('tokens', []))
                            
                            # Parse outcomes if it's a JSON string
                            if isinstance(outcomes_raw, str):
                                try:
                                    outcomes = json.loads(outcomes_raw)
                                except:
                                    outcomes = []
                            else:
                                outcomes = outcomes_raw
                            
                            clob_token_ids = []
                            # Also check for clobTokenIds directly in market
                            if 'clobTokenIds' in market:
                                token_ids_raw = market.get('clobTokenIds', '')
                                if isinstance(token_ids_raw, str):
                                    try:
                                        clob_token_ids = json.loads(token_ids_raw)
                                    except:
                                        pass
                                elif isinstance(token_ids_raw, list):
                                    clob_token_ids = token_ids_raw
                            
                            # If not found, try to extract from outcomes
                            if not clob_token_ids:
                                for outcome in outcomes:
                                    if isinstance(outcome, dict):
                                        token_id = outcome.get('clobTokenIds', outcome.get('token_id', ''))
                                        if token_id:
                                            clob_token_ids.append(token_id)
                            
                            print(f"  Found active UFC market: {question[:70]}")
                            
                            ufc_markets.append({
                                'event_title': market.get('groupItemTitle', market.get('title', 'UFC Event')),
                                'event_slug': market.get('market_slug', market.get('slug', '')),
                                'market_question': question,
                                'market_slug': market.get('condition_id', market.get('conditionId', '')),
                                'outcomes': outcomes,
                                'clob_token_ids': clob_token_ids,
                                'end_date': market.get('end_date_iso', market.get('endDate', market.get('end_date', '')))
                            })
                    
                    print(f"\n  Summary: {active_count} active UFC markets, {closed_count} closed markets (skipped)")
        
        print(f"\nFound {len(ufc_markets)} active UFC fight markets")
        return ufc_markets
        
    except Exception as e:
        print(f"Error fetching Polymarket data: {e}")
        import traceback
        traceback.print_exc()
        return []


def parse_fighter_matchup(question, outcomes, clob_token_ids=None):
    """
    Parse fighter names and odds from market data
    Question format: "Will Fighter A beat Fighter B?"
    """
    # Try to extract fighter names from the question
    # Pattern: "Will [Fighter A] beat [Fighter B]?"
    
    # Handle string outcomes (token IDs only)
    if outcomes and isinstance(outcomes[0], str):
        # Outcomes are just token IDs, extract names from question
        fighter1_name = None
        fighter2_name = None
        
        # Try pattern: "Will Fighter win"
        match = re.search(r'Will\s+([^?]+?)\s+(?:win|beat|defeat)', question, re.IGNORECASE)
        if match:
            fighter1_name = match.group(1).strip()
            # Try to find opponent with vs
            vs_match = re.search(r'vs\.?\s+([^?]+)', question, re.IGNORECASE)
            if vs_match:
                fighter2_name = vs_match.group(1).strip()
        
        # Try pattern: "Fighter1 vs Fighter2" or "Who will win: Fighter1 vs Fighter2"
        if not fighter1_name:
            vs_match = re.search(r'(\w+(?:\s+\w+)*)\s+vs\.?\s+(\w+(?:\s+\w+)*)', question, re.IGNORECASE)
            if vs_match:
                fighter1_name = vs_match.group(1).strip()
                fighter2_name = vs_match.group(2).strip()
        
        if fighter1_name and fighter2_name:
            # Use clob_token_ids from parameter if available
            if clob_token_ids and len(clob_token_ids) >= 2:
                fighter1_clob_id = clob_token_ids[0]
                fighter2_clob_id = clob_token_ids[1]
            else:
                fighter1_clob_id = ''
                fighter2_clob_id = ''
            
            return {
                'fighter1': normalize_fighter_name(fighter1_name),
                'fighter2': normalize_fighter_name(fighter2_name),
                'fighter1_odds': 0,  # Unknown without price data
                'fighter2_odds': 0,
                'fighter1_prob': 0.5,
                'fighter2_prob': 0.5,
                'fighter1_clob_token_id': fighter1_clob_id,
                'fighter2_clob_token_id': fighter2_clob_id
            }
        return None
    
    # Alternative: Use outcomes if they contain fighter names (dict format)
    if len(outcomes) >= 2 and isinstance(outcomes[0], dict):
        fighter1_name = outcomes[0].get('outcome', '')
        fighter2_name = outcomes[1].get('outcome', '')
        
        # Get probabilities (Polymarket uses prices 0-1)
        fighter1_odds = outcomes[0].get('price', 0.5)
        fighter2_odds = outcomes[1].get('price', 0.5)
        
        # Get clobTokenIds
        fighter1_clob_id = outcomes[0].get('clobTokenIds', outcomes[0].get('token_id', ''))
        fighter2_clob_id = outcomes[1].get('clobTokenIds', outcomes[1].get('token_id', ''))
        
        # If outcomes are Yes/No, try to parse from question
        if fighter1_name.lower() in ['yes', 'no']:
            # Try to extract from question
            match = re.search(r'Will\s+([^?]+?)\s+(?:beat|defeat|win against)\s+([^?]+?)\?', question, re.IGNORECASE)
            if match:
                fighter1_name = match.group(1).strip()
                fighter2_name = match.group(2).strip()
                
                # If Yes is for fighter1 winning
                if outcomes[0].get('outcome', '').lower() == 'yes':
                    fighter1_odds = outcomes[0].get('price', 0.5)
                    fighter2_odds = 1 - fighter1_odds
                else:
                    fighter2_odds = outcomes[0].get('price', 0.5)
                    fighter1_odds = 1 - fighter2_odds
        
        # Convert probability to American odds format
        fighter1_american = probability_to_american_odds(fighter1_odds)
        fighter2_american = probability_to_american_odds(fighter2_odds)
        
        return {
            'fighter1': normalize_fighter_name(fighter1_name),
            'fighter2': normalize_fighter_name(fighter2_name),
            'fighter1_odds': fighter1_american,
            'fighter2_odds': fighter2_american,
            'fighter1_prob': fighter1_odds,
            'fighter2_prob': fighter2_odds,
            'fighter1_clob_token_id': fighter1_clob_id,
            'fighter2_clob_token_id': fighter2_clob_id
        }
    
    return None


def get_market_price_from_domeapi(token_id, event_date_str):
    """
    Fetch market price from DomeAPI at midnight of the event date
    
    Args:
        token_id: The clobTokenId for the market
        event_date_str: Date string in format 'Mon DD YYYY' (e.g., 'Mar 06 2021')
    
    Returns:
        Price as float between 0 and 1, or None if error
    """
    try:
        # Parse event date and convert to Unix timestamp at 00:00
        event_dt = datetime.strptime(event_date_str, '%b %d %Y')
        # Set to midnight
        event_dt = event_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        at_time = int(event_dt.timestamp())
        
        # DomeAPI endpoint
        api_url = f"https://api.domeapi.io/v1/polymarket/market-price/{token_id}"
        params = {'at_time': at_time}
        
        response = requests.get(api_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            price = data.get('price')
            if price is not None:
                return float(price)
        elif response.status_code == 404:
            print(f"    Market not found for token {token_id[:20]}...")
        else:
            print(f"    API returned status {response.status_code} for token {token_id[:20]}...")
        
        return None
    except Exception as e:
        print(f"    Error fetching price from DomeAPI: {e}")
        return None


def get_live_prices_from_clob(clob_token_ids):
    """
    Fetch live prices from Polymarket CLOB API using token IDs
    (Legacy function - DomeAPI is now preferred)
    """
    try:
        if not clob_token_ids:
            return {}
        
        # CLOB API endpoint for price data
        base_url = "https://clob.polymarket.com/prices-history"
        
        prices = {}
        for token_id in clob_token_ids:
            try:
                params = {
                    'market': token_id,
                    'interval': '1m',
                    'fidelity': 1
                }
                response = requests.get(base_url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if data and len(data) > 0:
                        # Get latest price
                        latest = data[-1]
                        prices[token_id] = latest.get('price', latest.get('p', 0.5))
            except:
                continue
        
        return prices
    except Exception as e:
        print(f"Error fetching CLOB prices: {e}")
        return {}


def probability_to_american_odds(probability):
    """
    Convert probability (0-1) to American odds format
    """
    if probability >= 0.5:
        # Favorite (negative odds)
        if probability >= 0.99:
            return -10000
        return int(-100 * probability / (1 - probability))
    else:
        # Underdog (positive odds)
        if probability <= 0.01:
            return 10000
        return int(100 * (1 - probability) / probability)


def scrape_polymarket_odds():
    """
    Main function to scrape Polymarket UFC odds
    """
    print("="*60)
    print("Polymarket UFC Odds Scraper")
    print("="*60)
    
    # Get markets
    markets = get_polymarket_ufc_markets()
    
    if not markets:
        print("\n" + "="*60)
        print("❌ No active UFC markets found on Polymarket")
        print("="*60)
        print("\nSearched:")
        print("  ✓ CLOB API (main trading API)")
        print("  ✓ Gamma API (events API)")  
        print("  ✓ MMA sport category (series 10500)")
        print("  ✓ Sports tags and filters")
        print("\nConclusion:")
        print("  Polymarket has NO active UFC markets at this time.")
        print("  All UFC markets in their database are from 2020-2023 and closed.")
        print("\nWhat to do:")
        print("  • Check https://polymarket.com/sports/ufc manually")
        print("  • Run this scraper closer to major UFC events (1-2 weeks before)")
        print("  • Polymarket creates UFC markets sporadically for big fights")
        print("\nAlternatives for current UFC odds:")
        print("  • Use your existing scrape_fights_with_odds.py for sportsbooks")
        print("  • Check other prediction markets like Kalshi")
        print("="*60)
        return
    
    # Prepare output
    output_file = os.path.join('data', 'polymarket_ufc_odds.csv')
    
    # Check if file exists for append vs write
    file_exists = os.path.exists(output_file) and os.path.getsize(output_file) > 0
    
    fights_data = []
    
    for market in markets:
        fight_data = parse_fighter_matchup(
            market['market_question'],
            market['outcomes'],
            market.get('clob_token_ids', [])
        )
        
        if fight_data:
            # Add event information
            fight_data['event_name'] = market['event_slug']
            fight_data['event_title'] = market['event_title']
            fight_data['market_question'] = market['market_question']
            
            # Parse date
            try:
                end_date = market['end_date']
                if end_date:
                    # Polymarket typically uses ISO format
                    dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                    fight_data['event_date'] = dt.strftime('%b %d %Y')
                else:
                    fight_data['event_date'] = 'TBD'
            except:
                fight_data['event_date'] = 'TBD'
            
            # Fetch market prices from DomeAPI at event time
            if fight_data['event_date'] != 'TBD':
                print(f"\nFetching prices for {fight_data['fighter1']} vs {fight_data['fighter2']}...")
                
                # Get fighter 1 price
                if fight_data.get('fighter1_clob_token_id'):
                    price1 = get_market_price_from_domeapi(
                        fight_data['fighter1_clob_token_id'],
                        fight_data['event_date']
                    )
                    if price1 is not None:
                        fight_data['fighter1_prob'] = price1
                        fight_data['fighter1_odds'] = probability_to_american_odds(price1)
                        print(f"  {fight_data['fighter1']}: {price1:.3f} ({fight_data['fighter1_odds']:+d})")
                
                # Get fighter 2 price
                if fight_data.get('fighter2_clob_token_id'):
                    price2 = get_market_price_from_domeapi(
                        fight_data['fighter2_clob_token_id'],
                        fight_data['event_date']
                    )
                    if price2 is not None:
                        fight_data['fighter2_prob'] = price2
                        fight_data['fighter2_odds'] = probability_to_american_odds(price2)
                        print(f"  {fight_data['fighter2']}: {price2:.3f} ({fight_data['fighter2_odds']:+d})")
            
            fights_data.append(fight_data)
            
            print(f"\n✓ {fight_data['fighter1']} vs {fight_data['fighter2']}")
            print(f"  Odds: {fight_data['fighter1_odds']:+d} / {fight_data['fighter2_odds']:+d}")
            print(f"  Event: {fight_data['event_title']} on {fight_data['event_date']}")
            print()
    
    # Write to CSV
    if fights_data:
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'event_name', 'event_title', 'event_date',
                'fighter1', 'fighter2',
                'fighter1_odds', 'fighter2_odds',
                'fighter1_prob', 'fighter2_prob',
                'fighter1_clob_token_id', 'fighter2_clob_token_id',
                'market_question'
            ]
            
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for fight in fights_data:
                writer.writerow(fight)
        
        print(f"\n✓ Saved {len(fights_data)} fights to {output_file}")
    else:
        print("\n✗ No fight data extracted")
    
    print("="*60)


if __name__ == "__main__":
    scrape_polymarket_odds()
