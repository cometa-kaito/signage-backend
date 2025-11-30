import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Signage System"
    VERSION: str = "1.0.0"
    
    # セキュリティキー (本番環境では推測困難なランダム文字列を .env 等で設定してください)
    SECRET_KEY: str = os.getenv("SECRET_KEY", "super-secret-key")
    
    # サーバーのホストURL (画像の絶対パス生成やQRコード生成などで使用)
    HOST_URL: str = os.getenv("HOST_URL", "https://rebounder-signage.onrender.com")
    
    # データベースURL
    # デフォルトはプロジェクトルート直下の signage.db を指すように設定
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./signage.db")

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()