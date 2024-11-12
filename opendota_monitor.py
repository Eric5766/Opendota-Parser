import requests
import time
import json
import logging
from datetime import datetime, timezone
import os
from typing import List, Dict, Set
from dataclasses import dataclass
import sys

@dataclass
class Match:
    match_id: int
    start_time: int
    version: int | None

class OpenDotaMonitor:
    def __init__(self, player_ids: List[str], hours_threshold: int = 24, check_interval: int = 1200):
        self.player_ids = player_ids
        self.hours_threshold = hours_threshold
        self.check_interval = check_interval
        self.processed_matches = set()
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/app/data/opendota_monitor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        os.makedirs('/app/data', exist_ok=True)
        
        self._load_processed_matches()
            
        self.logger.info(f"Initialized monitor with {len(player_ids)} player IDs")
        self.logger.info(f"Monitoring players: {', '.join(player_ids)}")
        self.logger.info(f"Hours threshold: {hours_threshold}")
        self.logger.info(f"Check interval: {check_interval} seconds")

    def _load_processed_matches(self) -> None:
        try:
            with open('/app/data/processed_matches.json', 'r') as f:
                self.processed_matches = set(json.load(f))
            self.logger.info(f"Loaded {len(self.processed_matches)} processed match IDs")
        except FileNotFoundError:
            self.processed_matches = set()
            self.logger.info("No existing processed matches file found")

    def _save_processed_matches(self) -> None:
        try:
            with open('/app/data/processed_matches.json', 'w') as f:
                json.dump(list(self.processed_matches), f)
        except Exception as e:
            self.logger.error(f"Error saving processed matches: {e}")

    def _is_recent_game(self, start_time: int) -> bool:
        now = datetime.now(timezone.utc).timestamp()
        hours_old = (now - start_time) / 3600
        return hours_old < self.hours_threshold

    def _get_recent_matches(self, player_id: str) -> List[Match]:
        url = f"https://api.opendota.com/api/players/{player_id}/recentMatches"
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            matches_data = response.json()
            
            matches = []
            for match in matches_data:
                match_obj = Match(
                    match_id=match['match_id'],
                    start_time=match['start_time'],
                    version=match.get('version')
                )
                matches.append(match_obj)
            
            return matches
            
        except Exception as e:
            self.logger.error(f"Error fetching matches for player {player_id}: {str(e)}")
            return []

    def _get_unparsed_matches(self, player_id: str) -> List[int]:
        matches = self._get_recent_matches(player_id)
        unparsed_matches = []
        
        for match in matches:
            if not self._is_recent_game(match.start_time):
                continue
                
            if match.version is not None:
                continue
                
            if str(match.match_id) in self.processed_matches:
                continue
                
            unparsed_matches.append(match.match_id)
        
        return unparsed_matches

    def request_parse(self, match_id: int) -> bool:
        url = f"https://api.opendota.com/api/request/{match_id}"
        
        try:
            response = requests.post(url)
            response.raise_for_status()
            if response.status_code == 200:
                self.logger.info(f"Successfully requested parsing for match {match_id}")
                return True
            else:
                self.logger.error(f"Error requesting parse for match {match_id}: {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Error requesting parse for match {match_id}: {str(e)}")
            return False

    def run(self) -> None:
        self.logger.info("Starting OpenDota monitor...")
        
        while True:
            try:
                new_matches = set()

                for player_id in self.player_ids:
                    unparsed_matches = self._get_unparsed_matches(player_id)
                    new_matches.update(map(str, unparsed_matches))
                    
                    if unparsed_matches:
                        self.logger.info(f"Found {len(unparsed_matches)} unparsed matches for player {player_id}")
                
                for match_id in new_matches:
                    if match_id not in self.processed_matches:
                        if self.request_parse(int(match_id)):
                            self.processed_matches.add(match_id)
                            self._save_processed_matches()
                
                self.logger.info(f"Completed check. Sleeping for {self.check_interval} seconds...")
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.logger.error(f"Error in main loop: {str(e)}")
                self.logger.info("Retrying in 60 seconds...")
                time.sleep(60)

def get_player_ids() -> List[str]:
    player_ids_str = os.getenv('PLAYER_IDS')
    if not player_ids_str:
        raise ValueError("PLAYER_IDS environment variable is required")
    
    player_ids = [pid.strip() for pid in player_ids_str.split(',')]

    for pid in player_ids:
        if not pid.isdigit():
            raise ValueError(f"Invalid player ID: {pid}")
    
    return player_ids

def get_config() -> tuple[List[str], int, int]:
    player_ids = get_player_ids()
    hours_threshold = int(os.getenv('HOURS_THRESHOLD', '24'))
    check_interval = int(os.getenv('CHECK_INTERVAL', '1800'))
    
    return player_ids, hours_threshold, check_interval

if __name__ == "__main__":
    try:
        player_ids, hours_threshold, check_interval = get_config()
        monitor = OpenDotaMonitor(
            player_ids=player_ids,
            hours_threshold=hours_threshold,
            check_interval=check_interval
        )
        monitor.run()
    except Exception as e:
        logging.error(f"Failed to start monitor: {str(e)}")
        sys.exit(1)