from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer

# Clé secrète — sert à signer et vérifier les tokens
SECRET_KEY = "cle-secrete-temporaire-a-changer-en-production"
ALGORITHM = "HS256"
EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Utilisateur de test unique (en dur, comme convenu)
FAKE_USER = {
    "username": "user_test",
    "hashed_password": pwd_context.hash("test1234"),
}

def verify_user(username: str, password: str):
    if username != FAKE_USER["username"]:
        return False
    return pwd_context.verify(password, FAKE_USER["hashed_password"])

def create_token(username: str):
    expire = datetime.utcnow() + timedelta(minutes=EXPIRE_MINUTES)
    data = {"sub": username, "exp": expire}
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")