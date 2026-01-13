"""Expert Data Scrapers - Collect rankings and insights from fantasy experts"""
import requests
from bs4 import BeautifulSoup
import sqlite3
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
import time


class ExpertScrapers:
    """Scrapes fantasy basketball data from expert sources"""
    
    def __init__(self, db_path='data/fantasy_brain.db', cache_hours=24):
        self.db_path = db_path
        self.cache_hours = cache_hours
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def _is_cache_valid(self, player_name: str, source: str) -> bool:
        """Check if cached ranking is still valid"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT ranking_date FROM expert_rankings
                WHERE player_name = ? AND source = ?
                ORDER BY ranking_date DESC LIMIT 1
            ''', (player_name, source))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return False
            
            cache_date = datetime.strptime(row[0], '%Y-%m-%d').date()
            age_hours = (datetime.now().date() - cache_date).total_seconds() / 3600
            
            return age_hours < self.cache_hours
            
        except Exception as e:
            logger.debug(f"Cache check error: {e}")
            return False
    
    def _save_ranking(self, player_name: str, source: str, data: Dict):
        """Save expert ranking to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO expert_rankings (
                    player_name, source, ranking_date,
                    overall_rank, position_rank,
                    category_ranks, projected_stats,
                    start_sit_rating, expert_notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                player_name,
                source,
                datetime.now().date(),
                data.get('overall_rank'),
                data.get('position_rank'),
                json.dumps(data.get('category_ranks', {})),
                json.dumps(data.get('projected_stats', {})),
                data.get('start_sit_rating'),
                data.get('expert_notes', '')
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Error saving ranking: {e}")
    
    def scrape_fantasypros_rankings(self, limit: int = 200) -> Dict[str, Dict]:
        """
        Scrape top NBA players rankings (Now using Hashtag Basketball as source due to FP blocking)
        """
        try:
            # Hashtag Basketball rankings page
            url = "https://hashtagbasketball.com/fantasy-basketball-rankings"
            
            logger.info(f"🔍 Scraping Hashtag Basketball rankings...")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            rankings = {}
            
            # Hashtag table ID
            table = soup.find('table', {'id': 'ContentPlaceHolder1_GridView1'})
            
            if not table:
                logger.warning("⚠️ Could not find rankings table")
                return rankings
            
            rows = table.find_all('tr')
            
            # Skip header row
            for idx, row in enumerate(rows[1:limit+1], 1):
                try:
                    cols = row.find_all('td')
                    
                    if len(cols) < 5:
                        continue
                    
                    # Col 0: Rank
                    # Col 1: Player Name (inside 'a' usually, or just text)
                    player_cell = cols[1]
                    player_name = player_cell.get_text(strip=True)
                    
                    # Ignore repeated headers
                    if player_name.upper() == 'PLAYER':
                        continue
                    
                    # Clean up name (remove team abbr/notes if any)
                    # Hashtag is usually "Nikola Jokic" clean, but sometimes has "R" icon
                    if '\n' in player_name:
                        player_name = player_name.split('\n')[0].strip()
                    
                    rankings[player_name] = {
                        'overall_rank': idx,
                        'position_rank': None,
                        'start_sit_rating': 'START' if idx <= 100 else 'FLEX' if idx <= 150 else 'SIT',
                        'source': 'HASHTAG'
                    }
                    
                    # Save to cache
                    self._save_ranking(player_name, 'HASHTAG', rankings[player_name])
                    
                except Exception as e:
                    logger.debug(f"Error parsing row: {e}")
                    continue
            
            logger.info(f"✅ Scraped {len(rankings)} player rankings from Hashtag Basketball")
            
            return rankings
            
        except requests.RequestException as e:
            logger.error(f"❌ Hashtag scraping failed: {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ Unexpected error scraping Hashtag: {e}")
            return {}
    
    def scrape_rotowire_lineups(self) -> Dict[str, List[str]]:
        """
        Scrape Rotowire for confirmed starting lineups
        
        Returns: {
            'LAL': ['LeBron James', 'Anthony Davis', ...],
            'BOS': ['Jayson Tatum', 'Jaylen Brown', ...],
            ...
        }
        """
        try:
            url = "https://www.rotowire.com/basketball/nba-lineups.php"
            
            logger.info(f"🔍 Scraping Rotowire lineups...")
            
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            lineups = {}
            
            # Find lineup sections
            lineup_sections = soup.find_all('div', class_='lineup')
            
            for section in lineup_sections:
                try:
                    # Get team abbreviation
                    team_elem = section.find('div', class_='lineup__abbr')
                    if not team_elem:
                        continue
                    
                    team = team_elem.get_text(strip=True)
                    
                    # Get starters
                    starters_section = section.find('ul', class_='lineup__list')
                    if not starters_section:
                        continue
                    
                    starters = []
                    player_items = starters_section.find_all('li')
                    
                    for item in player_items[:5]:  # Top 5 = starters
                        player_name_elem = item.find('a')
                        if player_name_elem:
                            player_name = player_name_elem.get_text(strip=True)
                            starters.append(player_name)
                    
                    if starters:
                        lineups[team] = starters
                        logger.debug(f"  {team}: {len(starters)} starters")
                    
                except Exception as e:
                    logger.debug(f"Error parsing lineup section: {e}")
                    continue
            
            logger.info(f"✅ Scraped lineups for {len(lineups)} teams from Rotowire")
            
            # Rate limit
            time.sleep(2)
            
            return lineups
            
        except requests.RequestException as e:
            logger.error(f"❌ Rotowire scraping failed: {e}")
            return {}
        except Exception as e:
            logger.error(f"❌ Unexpected error scraping Rotowire: {e}")
            return {}
    
    def get_player_expert_data(self, player_name: str) -> Optional[Dict]:
        """
        Get aggregated expert data for a specific player
        
        Returns: {
            'fantasypros_rank': 45,
            'start_sit': 'START',
            'is_starter': True,
            'expert_confidence': 0.85
        }
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get latest ranking
            cursor.execute('''
                SELECT overall_rank, start_sit_rating, ranking_date
                FROM expert_rankings
                WHERE player_name = ?
                ORDER BY ranking_date DESC LIMIT 1
            ''', (player_name,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            rank, start_sit, date_str = row
            
            # Calculate confidence based on recency
            ranking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            days_old = (datetime.now().date() - ranking_date).days
            
            # Confidence decreases with age
            confidence = max(0.5, 1.0 - (days_old * 0.05))
            
            return {
                'fantasypros_rank': rank,
                'start_sit': start_sit,
                'expert_confidence': confidence,
                'days_since_update': days_old
            }
            
        except Exception as e:
            logger.debug(f"Error getting expert data for {player_name}: {e}")
            return None
    
    def aggregate_expert_consensus(self, player_name: str) -> Dict:
        """
        Combine all expert sources for a player
        
        Returns: {
            'overall_rank': 45,
            'consensus': 'START',
            'confidence': 0.85,
            'sources_count': 2
        }
        """
        expert_data = self.get_player_expert_data(player_name)
        
        if not expert_data:
            return {
                'overall_rank': 999,
                'consensus': 'UNKNOWN',
                'confidence': 0.0,
                'sources_count': 0
            }
        
        return {
            'overall_rank': expert_data['fantasypros_rank'],
            'consensus': expert_data['start_sit'],
            'confidence': expert_data['expert_confidence'],
            'sources_count': 1  # For now, just FantasyPros
        }
    
    def update_all_expert_data(self) -> Dict:
        """
        Update all expert data sources (daily job)
        
        Returns: Summary of what was updated
        """
        logger.info("🔄 Updating expert data...")
        
        summary = {
            'fantasypros_players': 0,
            'rotowire_teams': 0,
            'errors': []
        }
        
        try:
            # Update FantasyPros rankings
            rankings = self.scrape_fantasypros_rankings(limit=200)
            summary['fantasypros_players'] = len(rankings)
            
            # Update Rotowire lineups
            lineups = self.scrape_rotowire_lineups()
            summary['rotowire_teams'] = len(lineups)
            
            logger.info(f"✅ Expert data updated: {summary['fantasypros_players']} players, {summary['rotowire_teams']} teams")
            
        except Exception as e:
            error_msg = f"Error updating expert data: {e}"
            logger.error(f"❌ {error_msg}")
            summary['errors'].append(error_msg)
        
        return summary


# Testing
if __name__ == "__main__":
    from loguru import logger
    import sys
    
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    print("🔍 Testing Expert Scrapers...\n")
    
    scraper = ExpertScrapers()
    
    # Test FantasyPros
    print("1. Testing FantasyPros scraper...")
    rankings = scraper.scrape_fantasypros_rankings(limit=10)
    print(f"   ✅ Got {len(rankings)} rankings")
    if rankings:
        sample = list(rankings.items())[0]
        print(f"   Sample: {sample[0]} - Rank #{sample[1]['overall_rank']}")
    
    # Test Rotowire
    print("\n2. Testing Rotowire scraper...")
    lineups = scraper.scrape_rotowire_lineups()
    print(f"   ✅ Got lineups for {len(lineups)} teams")
    if lineups:
        sample_team = list(lineups.items())[0]
        print(f"   Sample: {sample_team[0]} starters: {', '.join(sample_team[1][:3])}...")
    
    # Test aggregation
    if rankings:
        print("\n3. Testing expert data aggregation...")
        player = list(rankings.keys())[0]
        data = scraper.get_player_expert_data(player)
        print(f"   Player: {player}")
        print(f"   Data: {data}")
    
    print("\n✅ Expert Scrapers ready!")
