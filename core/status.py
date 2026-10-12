"""
Status Analyzer module for determining user online status
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from enum import Enum

from utils.logger import get_logger
from utils.helpers import (
    get_online_status,
    calculate_online_probability,
    parse_activity_level
)
from config.config import get_config


class StatusSource(Enum):
    """Sources for status determination"""
    TYPING_INDICATOR = "typing"
    MESSAGE_TIMESTAMP = "message_timestamp"
    READ_RECEIPT = "read_receipt"
    API_STATUS = "api_status"
    LAST_SEEN_TIME = "last_seen_time"
    CALL_STATUS = "call_status"


class StatusAnalyzer:
    """Analyzes and determines user online status from multiple signals"""
    
    def __init__(self):
        self.logger = get_logger()
        self.config = get_config()
        self.status_cache: Dict[int, Dict] = {}
        self.status_history: Dict[int, List[Tuple[datetime, str]]] = {}
    
    def analyze_user_status(
        self,
        user_id: int,
        typing_activity: bool = False,
        recent_message_time: Optional[datetime] = None,
        read_receipt: bool = False,
        api_status: Optional[bool] = None,
        last_seen: Optional[datetime] = None
    ) -> Dict:
        """
        Analyze user status from multiple signals
        
        Args:
            user_id: User ID
            typing_activity: Is user currently typing
            recent_message_time: Timestamp of last message
            read_receipt: Has user read recent messages
            api_status: API status check result
            last_seen: Last seen timestamp
            
        Returns:
            Status analysis dictionary
        """
        config = get_config()
        threshold_minutes = config.get('check_online_threshold_minutes', 5)
        
        # Determine if online based on signals
        is_online = False
        probability = 0.0
        primary_indicator = None
        sources_used = []
        
        # Check typing activity (strongest indicator)
        if config.get('track_typing', True) and typing_activity:
            is_online = True
            primary_indicator = "User is typing"
            sources_used.append(StatusSource.TYPING_INDICATOR)
            probability = 0.95
        
        # Check recent message timestamp
        if config.get('track_message_timestamps', True) and recent_message_time:
            time_diff = datetime.now() - recent_message_time
            minutes_ago = time_diff.total_seconds() / 60
            
            if minutes_ago <= threshold_minutes:
                is_online = True
                if not primary_indicator:
                    primary_indicator = f"Message sent {int(minutes_ago)} minutes ago"
                sources_used.append(StatusSource.MESSAGE_TIMESTAMP)
                probability = max(probability, 0.85)
        
        # Check read receipts
        if config.get('track_read_receipts', True) and read_receipt:
            time_diff = datetime.now() - recent_message_time if recent_message_time else timedelta(hours=1)
            if time_diff.total_seconds() / 60 <= 10:
                is_online = True
                if not primary_indicator:
                    primary_indicator = "Recently read message"
                sources_used.append(StatusSource.READ_RECEIPT)
                probability = max(probability, 0.80)
        
        # Check API status (if available)
        if config.get('use_api_check', True) and api_status is not None:
            sources_used.append(StatusSource.API_STATUS)
            if api_status:
                is_online = True
                probability = max(probability, 0.90)
        
        # Check last seen time
        if last_seen:
            time_diff = datetime.now() - last_seen
            minutes_ago = time_diff.total_seconds() / 60
            
            if minutes_ago <= threshold_minutes:
                is_online = True
                if not primary_indicator:
                    primary_indicator = f"Last seen {int(minutes_ago)} minutes ago"
                sources_used.append(StatusSource.LAST_SEEN_TIME)
                probability = max(probability, 0.75)
        
        # Calculate probability from multiple signals
        if not sources_used:
            probability = 0.0
            status_text = "🔴 No activity data"
        else:
            probability = calculate_online_probability(
                typing_activity=typing_activity,
                recent_message_time=recent_message_time is not None and 
                                   (datetime.now() - recent_message_time).total_seconds() / 60 <= threshold_minutes,
                read_receipt=read_receipt,
                api_status=api_status
            )
            
            if probability >= 0.75:
                status_text = "🟢 Online"
            elif probability >= 0.50:
                status_text = "🟡 Likely Online"
            elif probability >= 0.25:
                status_text = "🟠 Recently Active"
            else:
                status_text = "⚫ Offline"
        
        analysis = {
            'user_id': user_id,
            'is_online': is_online,
            'probability': probability,
            'status_text': status_text,
            'primary_indicator': primary_indicator,
            'sources_used': [s.value for s in sources_used],
            'confidence': len(sources_used) / 6,  # Max 6 sources
            'timestamp': datetime.now(),
            'analysis_details': {
                'typing': typing_activity,
                'recent_message': recent_message_time is not None,
                'read_receipt': read_receipt,
                'api_status': api_status,
                'last_seen': last_seen
            }
        }
        
        # Cache result
        self.status_cache[user_id] = analysis
        
        # Store in history
        if user_id not in self.status_history:
            self.status_history[user_id] = []
        self.status_history[user_id].append((datetime.now(), status_text))
        
        # Keep only last 1000 history entries
        if len(self.status_history[user_id]) > 1000:
            self.status_history[user_id] = self.status_history[user_id][-1000:]
        
        self.logger.debug(
            f"Status analyzed for user {user_id}: {status_text} "
            f"(probability: {probability:.2%}, sources: {len(sources_used)})"
        )
        
        return analysis
    
    def get_cached_status(self, user_id: int) -> Optional[Dict]:
        """Get cached status for user"""
        return self.status_cache.get(user_id)
    
    def get_status_history(self, user_id: int, hours: int = 24) -> List[Tuple[datetime, str]]:
        """Get status history for user"""
        if user_id not in self.status_history:
            return []
        
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [
            (ts, status) for ts, status in self.status_history[user_id]
            if ts > cutoff_time
        ]
    
    def get_online_percentage(self, user_id: int, hours: int = 24) -> float:
        """Calculate percentage of time user was online in the last N hours"""
        history = self.get_status_history(user_id, hours)
        
        if not history:
            return 0.0
        
        online_time = sum(
            1 for _, status in history
            if status.startswith('🟢') or status.startswith('🟡')
        )
        
        return (online_time / len(history)) * 100 if history else 0.0
    
    def get_activity_level(
        self,
        message_count: int,
        last_seen_minutes: int
    ) -> str:
        """Get activity level based on message count and time"""
        return parse_activity_level(message_count, last_seen_minutes)
    
    def clear_cache(self) -> None:
        """Clear status cache"""
        self.status_cache.clear()
        self.logger.info("Status cache cleared")
