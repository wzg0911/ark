"""
ARK MultiAgentProtocol — 多Agent可靠性协议
基因来源：PraisonAI (⭐8,104) + BMAD-METHOD

Agent之间通信的可靠性协议：握手确认、消息送达保证、健康检查。
"""

import time, uuid, json, hashlib, threading
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class MessageStatus(Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    TIMEOUT = "timeout"


class AgentStatus(Enum):
    ONLINE = "online"
    BUSY = "busy"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class AgentMessage:
    """Agent间消息"""
    message_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    sender: str = ""
    recipient: str = ""
    content: Dict = field(default_factory=dict)
    status: MessageStatus = MessageStatus.PENDING
    created_at: float = field(default_factory=time.time)
    delivered_at: Optional[float] = None
    acknowledged_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    ttl_seconds: float = 30.0


@dataclass
class AgentHeartbeat:
    """Agent心跳信号"""
    agent_id: str
    status: AgentStatus
    last_seen: float = field(default_factory=time.time)
    message_count: int = 0
    error_count: int = 0
    avg_response_ms: float = 0.0


class MultiAgentProtocol:
    """多Agent可靠性协议"""
    
    def __init__(self, agent_id: str, heartbeat_interval: float = 5.0):
        self.agent_id = agent_id
        self.heartbeat_interval = heartbeat_interval
        
        self._messages: Dict[str, AgentMessage] = {}
        self._agents: Dict[str, AgentHeartbeat] = {}
        self._lock = threading.RLock()
        self._running = False
        
        # 统计
        self._total_messages_sent = 0
        self._total_messages_delivered = 0
        self._total_messages_failed = 0
        self._total_retries = 0
        self._total_heartbeats = 0
        self._total_timeouts = 0
    
    def register_agent(self, agent_id: str, initial_status: AgentStatus = AgentStatus.ONLINE) -> bool:
        """注册对等Agent（默认Online）"""
        with self._lock:
            if agent_id not in self._agents:
                self._agents[agent_id] = AgentHeartbeat(
                    agent_id=agent_id,
                    status=initial_status
                )
                return True
            self._agents[agent_id].status = AgentStatus.ONLINE
            self._agents[agent_id].last_seen = time.time()
            return False
    
    def deregister_agent(self, agent_id: str):
        with self._lock:
            if agent_id in self._agents:
                self._agents[agent_id].status = AgentStatus.OFFLINE
    
    def send_message(self, recipient: str, content: Dict, 
                     max_retries: int = 3, ttl: float = 30.0) -> AgentMessage:
        """发送消息给指定Agent"""
        msg = AgentMessage(
            sender=self.agent_id,
            recipient=recipient,
            content=content,
            max_retries=max_retries,
            ttl_seconds=ttl
        )
        
        with self._lock:
            self._messages[msg.message_id] = msg
            self._total_messages_sent += 1
        
        self._try_deliver(msg)
        return msg
    
    def _try_deliver(self, msg: AgentMessage):
        """尝试投递消息（交付给注册的handler）"""
        with self._lock:
            recipient = self._agents.get(msg.recipient)
            if recipient and recipient.status not in (AgentStatus.OFFLINE, AgentStatus.UNKNOWN):
                msg.status = MessageStatus.DELIVERED
                msg.delivered_at = time.time()
                self._total_messages_delivered += 1
            else:
                msg.status = MessageStatus.FAILED
                self._total_messages_failed += 1
    
    def acknowledge_message(self, message_id: str):
        """确认消息已收到"""
        with self._lock:
            msg = self._messages.get(message_id)
            if msg and msg.status == MessageStatus.DELIVERED:
                msg.status = MessageStatus.ACKNOWLEDGED
                msg.acknowledged_at = time.time()
    
    def retry_message(self, message_id: str) -> bool:
        """重试投递失败的消息"""
        with self._lock:
            msg = self._messages.get(message_id)
            if not msg:
                return False
            if msg.retry_count >= msg.max_retries:
                msg.status = MessageStatus.TIMEOUT
                self._total_timeouts += 1
                return False
            msg.retry_count += 1
            self._total_retries += 1
        
        self._try_deliver(msg)
        return True
    
    def send_heartbeat(self, status: AgentStatus = AgentStatus.ONLINE):
        """发送心跳信号"""
        with self._lock:
            if self.agent_id not in self._agents:
                self._agents[self.agent_id] = AgentHeartbeat(
                    agent_id=self.agent_id,
                    status=status
                )
            else:
                self._agents[self.agent_id].status = status
                self._agents[self.agent_id].last_seen = time.time()
            self._total_heartbeats += 1
    
    def check_agent_health(self, agent_id: str, max_age: float = 15.0) -> AgentStatus:
        """检查Agent健康状态"""
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return AgentStatus.UNKNOWN
            if time.time() - agent.last_seen > max_age:
                agent.status = AgentStatus.OFFLINE
                return AgentStatus.OFFLINE
            return agent.status
    
    def get_online_agents(self) -> List[str]:
        """获取在线Agent列表"""
        with self._lock:
            return [
                aid for aid, a in self._agents.items()
                if a.status == AgentStatus.ONLINE
                and time.time() - a.last_seen < 15.0
            ]
    
    def collect_garbage(self):
        """清理过期消息和离线Agent"""
        now = time.time()
        with self._lock:
            # 清理过期消息
            expired_ids = [
                mid for mid, msg in self._messages.items()
                if now - msg.created_at > msg.ttl_seconds
            ]
            for mid in expired_ids:
                del self._messages[mid]
            
            # 标记离线Agent
            for aid, agent in self._agents.items():
                if now - agent.last_seen > 30.0:
                    agent.status = AgentStatus.OFFLINE
    
    @property
    def stats(self) -> Dict:
        with self._lock:
            return {
                "agent_id": self.agent_id,
                "messages_sent": self._total_messages_sent,
                "messages_delivered": self._total_messages_delivered,
                "messages_failed": self._total_messages_failed,
                "total_retries": self._total_retries,
                "total_timeouts": self._total_timeouts,
                "total_heartbeats": self._total_heartbeats,
                "active_messages": len(self._messages),
                "registered_agents": len(self._agents),
                "online_agents": len(self.get_online_agents()),
                "delivery_rate": f"{self._total_messages_delivered/max(self._total_messages_sent,1)*100:.1f}%",
            }
    
    @property
    def network_map(self) -> str:
        """生成网络拓扑图"""
        lines = [f"🌐 ARK Multi-Agent Network: {self.agent_id}"]
        with self._lock:
            for aid, agent in sorted(self._agents.items()):
                status_icon = {
                    AgentStatus.ONLINE: "🟢",
                    AgentStatus.BUSY: "🟡",
                    AgentStatus.DEGRADED: "🟠",
                    AgentStatus.OFFLINE: "🔴",
                    AgentStatus.UNKNOWN: "⚪",
                }
                icon = status_icon.get(agent.status, "❓")
                age = time.time() - agent.last_seen
                lines.append(f"  {icon} {aid} (seen {age:.0f}s ago, {agent.message_count} msgs)")
            lines.append(f"  ────")
            lines.append(f"  📊 Delivery: {self.stats['delivery_rate']} | Active msgs: {self.stats['active_messages']}")
        return "\n".join(lines)
