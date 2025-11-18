"""
Script pour vérifier l'état de Celery et déboguer le problème de notification all_users
"""
import sys
import os

# Ajouter le répertoire parent au PATH pour les imports
sys.path.insert(0, os.path.abspath('.'))

def test_celery_status():
    """Test du statut Celery"""
    print("🔍 Vérification de l'état de Celery")
    print("=" * 50)
    
    try:
        from app.celery_app import celery_app
        print("✅ Import celery_app réussi")
        
        # Vérifier la connexion au broker
        try:
            inspect = celery_app.control.inspect()
            stats = inspect.stats()
            
            if stats:
                print(f"✅ Celery workers actifs: {len(stats)}")
                for worker_name, worker_stats in stats.items():
                    print(f"   Worker: {worker_name}")
                    print(f"   Pool: {worker_stats.get('pool', {}).get('max-concurrency', 'N/A')} concurrent")
            else:
                print("⚠️  Aucun worker Celery détecté")
                print("   Démarrez un worker avec: celery -A app.celery_app worker --loglevel=info")
                
        except Exception as e:
            print(f"❌ Erreur connexion Celery: {str(e)}")
            print("   Vérifiez que RabbitMQ est démarré")
            
    except Exception as e:
        print(f"❌ Erreur import Celery: {str(e)}")
        return False
        
    return True

def test_batch_task_import():
    """Test de l'import des tâches batch"""
    print("\n🔍 Vérification des tâches batch")
    print("=" * 50)
    
    try:
        from app.tasks.batch_tasks import send_broadcast_notifications
        print("✅ Import send_broadcast_notifications réussi")
        
        # Vérifier la tâche
        task_info = send_broadcast_notifications
        print(f"   Nom de la tâche: {task_info.name}")
        print(f"   Type: {type(task_info)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur import batch_tasks: {str(e)}")
        return False

def test_simple_task():
    """Test d'une tâche simple"""
    print("\n🔍 Test d'une tâche Celery simple")
    print("=" * 50)
    
    try:
        from app.tasks.simple_tasks import test_task
        
        # Essayer d'envoyer une tâche test
        result = test_task.delay("Test de notification")
        print(f"✅ Tâche test envoyée: ID = {result.id}")
        
        # Attendre le résultat (max 5 secondes)
        import time
        for i in range(5):
            if result.ready():
                print(f"✅ Tâche terminée: {result.result}")
                return True
            print(f"   Attente... ({i+1}/5)")
            time.sleep(1)
            
        print("⚠️  Tâche toujours en cours après 5 secondes")
        print(f"   Status: {result.status}")
        return False
        
    except Exception as e:
        print(f"❌ Erreur test tâche: {str(e)}")
        return False

def main():
    print("🚀 Diagnostic Celery pour SamaConso")
    print("=" * 60)
    
    # Tests séquentiels
    celery_ok = test_celery_status()
    batch_ok = test_batch_task_import()
    
    if celery_ok:
        task_ok = test_simple_task()
    else:
        task_ok = False
        
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DU DIAGNOSTIC")
    print("=" * 60)
    
    print(f"Celery configuré: {'✅' if celery_ok else '❌'}")
    print(f"Tâches batch disponibles: {'✅' if batch_ok else '❌'}")
    print(f"Workers opérationnels: {'✅' if task_ok else '❌'}")
    
    if not task_ok:
        print("\n💡 Solutions possibles:")
        print("1. Démarrer RabbitMQ: docker run -d -p 5672:5672 -p 15672:15672 rabbitmq:3-management")
        print("2. Démarrer Redis: docker run -d -p 6379:6379 redis:alpine")
        print("3. Démarrer Celery worker: celery -A app.celery_app worker --loglevel=info")
        print("4. Ou utiliser le script: python start_celery_worker.bat")
        
    return celery_ok and batch_ok and task_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)