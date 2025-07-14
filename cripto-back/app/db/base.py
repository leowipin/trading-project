from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from core.config import settings # Importamos la configuración

# URL de conexión (ya no está hardcodeada aquí)
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Creamos el motor asíncrono de SQLAlchemy
engine = create_async_engine(str(SQLALCHEMY_DATABASE_URL))

# Creamos una fábrica de sesiones asíncronas
AsyncSessionLocal = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Creamos una clase Base para que nuestros modelos de ORM la hereden
Base = declarative_base()