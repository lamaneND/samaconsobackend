@echo off
REM Script pour envoyer une notification test
REM Utilisation: send_test_notification.bat [user_id]

setlocal

if "%1"=="" (
    set USER_ID=9
    echo Aucun user_id specifie, utilisation de user_id=9
) else (
    set USER_ID=%1
    echo Utilisation de user_id=%USER_ID%
)

echo ============================================================
echo   Envoi de Notification Test
echo ============================================================
echo.

echo [1/2] Recuperation du token FCM pour user_id=%USER_ID%...
echo.

docker exec samaconso_api python -c "
from app.database import get_db_samaconso
from app.models.models import UserSession
from app.firebase import send_pushNotification
from app.schemas.notification_schemas import PushNotification
import asyncio

# Récupérer le token
db = next(get_db_samaconso())
session = db.query(UserSession).filter(
    UserSession.user_id == %USER_ID%,
    UserSession.fcm_token.isnot(None),
    UserSession.fcm_token != '',
    UserSession.is_active == True
).first()

if not session:
    print('❌ Aucun token FCM actif trouvé pour user_id=%USER_ID%')
    exit(1)

print(f'✅ Token trouvé pour user_id={session.user_id}')
print(f'Token: {session.fcm_token[:50]}...')
print()

# Envoyer la notification
print('[2/2] Envoi de la notification...')
print()

test_notif = PushNotification(
    token=session.fcm_token,
    title='🔔 Test SamaConso',
    body='Notification de test envoyée depuis Docker. Tout fonctionne correctement!'
)

loop = asyncio.new_event_loop()
result = loop.run_until_complete(send_pushNotification(test_notif))
loop.close()

print(f'Status Code: {result.status_code}')
if result.status_code == 200:
    print('✅ SUCCESS: Notification envoyée avec succès!')
    print('📱 Vérifiez votre téléphone maintenant.')
    print()
    print('Message ID:', result.json().get('name', 'N/A'))
elif result.status_code == 404:
    print('❌ ERROR: Token invalide ou expiré')
    print('Conseil: Reconnectez-vous avec l application mobile')
elif result.status_code == 400:
    print('⚠️ WARNING: Requête invalide')
    print('Détails:', result.text[:200])
else:
    print(f'⚠️ Status inattendu: {result.status_code}')
    print('Response:', result.text[:200])
"

echo.
echo ============================================================
echo   Terminé
echo ============================================================
echo.

if %ERRORLEVEL% NEQ 0 (
    echo [31mErreur lors de l'envoi de la notification[0m
) else (
    echo [32mNotification envoyée avec succès![0m
)

echo.
pause
