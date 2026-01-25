"""External tool integrations."""
from app.integrations.streamrip import StreamripClient, StreamripError
from app.integrations.ytdlp import YtdlpClient, YtdlpError
from app.integrations.beets import BeetsClient, BeetsError
from app.integrations.exiftool import ExifToolClient, quality_score
from app.integrations.torrentleech import TorrentLeechClient, TorrentLeechError
from app.integrations.lidarr import LidarrClient, LidarrError
from app.integrations.bandcamp import BandcampClient, BandcampError

__all__ = [
    "StreamripClient",
    "StreamripError",
    "YtdlpClient",
    "YtdlpError",
    "BeetsClient",
    "BeetsError",
    "ExifToolClient",
    "quality_score",
    "TorrentLeechClient",
    "TorrentLeechError",
    "LidarrClient",
    "LidarrError",
    "BandcampClient",
    "BandcampError",
]
