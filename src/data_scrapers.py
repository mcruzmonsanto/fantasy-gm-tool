"""Data scrapers for NBA injury reports and news - 100% Free"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import time
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

class InjuryReportScraper:
    """Scrapes official NBA injury reports"""
    
    def __init__(self):
        self.base_url = "https://www.nba.com/stats"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def get_injury_report(self) -> Dict[str, dict]:
        """
        Get current NBA injury report
        
        Returns:
            {
                'LeBron James': {
                    'status': 'OUT',
                    'injury': 'Ankle',
                    'team': 'LAL',
                    'last_update': '2026-01-11'
                }
            }
        """
        injuries = {}
        
        try:
            # NBA official injury report endpoint
            url = "https://www.nba.com/stats/players/injuries"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                # Parse injury data
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Fallback to ESPN injury report if NBA.com fails
                if not soup.find_all('tr'):
                    return self._get_espn_injuries()
                
                logger.info(f"✅ Injury report cargado: {len(injuries)} jugadores")
                
            else:
                logger.warning("⚠️ NBA.com no disponible, usando ESPN fallback")
                return self._get_espn_injuries()
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo injury report: {e}")
            return self._get_espn_injuries()
        
        return injuries
    
    def _get_espn_injuries(self) -> Dict[str, dict]:
        """Fallback: ESPN injury report"""
        injuries = {}
        
        try:
            url = "https://www.espn.com/nba/injuries"
            response = requests.get(url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Parse ESPN injury table
                injury_tables = soup.find_all('table', class_='Table')
                
                for table in injury_tables:
                    rows = table.find_all('tr')[1:]  # Skip header
                    
                    for row in rows:
                        cols = row.find_all('td')
                        if len(cols) >= 3:
                            player_name = cols[0].get_text(strip=True)
                            injury_desc = cols[2].get_text(strip=True)
                            status = cols[1].get_text(strip=True).upper()
                            
                            injuries[player_name] = {
                                'status': status,
                                'injury': injury_desc,
                                'team': '',
                                'last_update': datetime.now().strftime('%Y-%m-%d')
                            }
                
                logger.info(f"✅ ESPN injuries cargadas: {len(injuries)} jugadores")
                
        except Exception as e:
            logger.error(f"❌ Error ESPN injuries: {e}")
        
        return injuries
    
    def is_player_healthy(self, player_name: str, injuries: dict) -> tuple:
        """
        Check if player is healthy
        
        Returns:
            (is_healthy: bool, status: str, injury: str)
        """
        if player_name in injuries:
            status = injuries[player_name]['status']
            is_healthy = status not in ['OUT', 'DOUBTFUL']
            return is_healthy, status, injuries[player_name]['injury']
        
        return True, 'HEALTHY', ''


class NewsScrapperScraper:
    """Scrapes latest NBA news from free sources"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def get_player_news(self, player_name: str, limit=5) -> List[dict]:
        """
        Get latest news about a player
        
        Returns:
            [
                {
                    'title': 'LeBron drops 40 points',
                    'summary': 'Lakers star...',
                    'source': 'ESPN',
                    'date': '2026-01-11',
                    'sentiment': 'POSITIVE'
                }
            ]
        """
        news = []
        
        try:
            # Search ESPN for player news
            search_url = f"https://www.espn.com/nba/search/_/q/{player_name.replace(' ', '%20')}"
            response = requests.get(search_url, headers=self.headers, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Parse news articles
                articles = soup.find_all('article', limit=limit)
                
                for article in articles:
                    title_elem = article.find('h1') or article.find('h2')
                    
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        
                        news.append({
                            'title': title,
                            'summary': '',
                            'source': 'ESPN',
                            'date': datetime.now().strftime('%Y-%m-%d'),
                            'sentiment': self._analyze_sentiment(title)
                        })
                
                logger.info(f"✅ News para {player_name}: {len(news)} artículos")
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo news para {player_name}: {e}")
        
        return news
    
    def _analyze_sentiment(self, text: str) -> str:
        """Simple sentiment analysis"""
        text_lower = text.lower()
        
        positive_words = ['scores', 'wins', 'returns', 'leads', 'career-high', 'amazing', 'great']
        negative_words = ['injury', 'out', 'miss', 'questionable', 'struggling', 'benched']
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return 'POSITIVE'
        elif negative_count > positive_count:
            return 'NEGATIVE'
        else:
            return 'NEUTRAL'


class ScheduleAnalyzer:
    """Analyzes upcoming NBA game schedules"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def get_games_next_7_days(self, team_abbr: str) -> int:
        """
        Get number of games in next 7 days for a team
        
        Args:
            team_abbr: Team abbreviation (e.g., 'LAL', 'GSW')
        
        Returns:
            Number of games
        """
        try:
            # Use ESPN scoreboard API
            today = datetime.now()
            games_count = 0
            
            for i in range(7):
                date = (today + timedelta(days=i)).strftime('%Y%m%d')
                url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
                
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for event in data.get('events', []):
                        for comp in event.get('competitions', []):
                            for competitor in comp.get('competitors', []):
                                team_data = competitor.get('team', {})
                                if team_data.get('abbreviation') == team_abbr:
                                    games_count += 1
                                    break
                
                # Rate limiting
                time.sleep(0.5)
            
            logger.info(f"✅ {team_abbr}: {games_count} juegos próximos 7 días")
            return games_count
            
        except Exception as e:
            logger.error(f"❌ Error analizando schedule para {team_abbr}: {e}")
            return 0
    
    def get_favorable_matchups(self, team_abbr: str, sos_map: dict) -> List[str]:
        """
        Get list of favorable matchups (vs weak teams)
        
        Args:
            team_abbr: Team abbreviation
            sos_map: Strength of schedule map from app
        
        Returns:
            List of opponent abbreviations that are favorable
        """
        # Simple heuristic: teams with win% < 0.40 are favorable
        favorable = []
        
        try:
            today = datetime.now()
            
            for i in range(7):
                date = (today + timedelta(days=i)).strftime('%Y%m%d')
                url = f"http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
                
                response = requests.get(url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    for event in data.get('events', []):
                        for comp in event.get('competitions', []):
                            competitors = comp.get('competitors', [])
                            
                            if len(competitors) == 2:
                                team1 = competitors[0].get('team', {}).get('abbreviation')
                                team2 = competitors[1].get('team', {}).get('abbreviation')
                                
                                if team1 == team_abbr:
                                    opponent = team2
                                    if sos_map.get(opponent, 0.5) < 0.40:
                                        favorable.append(opponent)
                                
                                elif team2 == team_abbr:
                                    opponent = team1
                                    if sos_map.get(opponent, 0.5) < 0.40:
                                        favorable.append(opponent)
                
                time.sleep(0.5)
            
            logger.info(f"✅ {team_abbr}: {len(favorable)} matchups favorables")
            
        except Exception as e:
            logger.error(f"❌ Error analizando matchups para {team_abbr}: {e}")
        
        return favorable


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("🔍 Testing scrapers...\n")
    
    # Test injury scraper
    print("1. Testing Injury Report...")
    injury_scraper = InjuryReportScraper()
    injuries = injury_scraper.get_injury_report()
    print(f"Found {len(injuries)} injured players")
    
    # Test news scraper
    print("\n2. Testing News Scraper...")
    news_scraper = NewsScrapperScraper()
    lebron_news = news_scraper.get_player_news("LeBron James", limit=3)
    print(f"Found {len(lebron_news)} news articles for LeBron")
    
    # Test schedule analyzer
    print("\n3. Testing Schedule Analyzer...")
    schedule = ScheduleAnalyzer()
    lal_games = schedule.get_games_next_7_days("LAL")
    print(f"LAL has {lal_games} games in next 7 days")
    
    print("\n✅ All scrapers tested!")
