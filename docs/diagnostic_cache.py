#!/usr/bin/env python3
"""
Diagnostic du cache user_compteur
"""
import requests
import json
import time

def diagnostic_cache_user_compteur():
    base_url = 'http://127.0.0.1:8000'
    
    print('🔍 DIAGNOSTIC COMPLET DU CACHE USER_COMPTEUR')
    print('=' * 50)
    
    # 1. État initial du cache
    print('\n1️⃣ État initial du cache:')
    resp = requests.get(f'{base_url}/user_compteur/cache/inspect')
    if resp.status_code == 200:
        cache_info = resp.json()
        print(f'  Total actif: {cache_info["total_active"]}')
        print(f'  Clés actives: {len(cache_info.get("active_keys", []))}')
    else:
        print(f'  ❌ Erreur inspection: {resp.status_code}')
    
    # 2. Exécution requête GET
    print('\n2️⃣ Exécution GET /user_compteur/:')
    start_time = time.time()
    resp = requests.get(f'{base_url}/user_compteur/')
    end_time = time.time()
    
    if resp.status_code == 200:
        data = resp.json()
        print(f'  ✅ Succès: {len(data)} user_compteurs récupérés')
        print(f'  ⏱️ Temps: {end_time - start_time:.3f}s')
    else:
        print(f'  ❌ Erreur GET: {resp.status_code}')
        return
    
    # 3. Vérification cache après requête
    print('\n3️⃣ État du cache APRÈS la requête:')
    time.sleep(0.5)  # Attendre que le cache se mette à jour
    resp = requests.get(f'{base_url}/user_compteur/cache/inspect')
    if resp.status_code == 200:
        cache_info = resp.json()
        total_active = cache_info.get('total_active', 0)
        active_keys = cache_info.get('active_keys', [])
        
        print(f'  Total actif: {total_active}')
        
        if total_active > 0:
            print('  ✅ CACHE FONCTIONNE!')
            for key_info in active_keys:
                key_name = key_info.get('key', 'N/A')
                key_size = key_info.get('size', 0)
                print(f'    - {key_name}: {key_size} chars')
        else:
            print('  ❌ CACHE VIDE - Problème détecté!')
            print('  🔍 Causes possibles:')
            print('    • Erreur dans la fonction cache_set')
            print('    • Redis non connecté')
            print('    • TTL trop court')
            print('    • Exception dans le code de cache')
    
    # 4. Test Redis direct
    print('\n4️⃣ Test Redis direct:')
    try:
        # Vérifier si Redis fonctionne
        resp = requests.get(f'{base_url}/user_compteur/cache/inspect')
        if resp.status_code == 200:
            print('  ✅ Endpoint d\'inspection accessible')
        else:
            print('  ❌ Endpoint d\'inspection inaccessible')
    except Exception as e:
        print(f'  ❌ Erreur: {e}')
    
    # 5. Test d'une seconde requête pour cache hit
    print('\n5️⃣ Test seconde requête (cache hit test):')
    start_time = time.time()
    resp = requests.get(f'{base_url}/user_compteur/')
    end_time = time.time()
    
    if resp.status_code == 200:
        data = resp.json()
        print(f'  ✅ Succès: {len(data)} user_compteurs')
        print(f'  ⏱️ Temps: {end_time - start_time:.3f}s')
        
        # Comparer les temps pour détecter le cache hit
        if end_time - start_time < 0.01:
            print('  🚀 TRÈS RAPIDE - Cache hit probable!')
        elif end_time - start_time < 0.05:
            print('  ⚡ Rapide - Possible cache hit')
        else:
            print('  🐌 Lent - Probablement depuis BDD (pas de cache)')
    
    print('\n' + '=' * 50)

if __name__ == "__main__":
    try:
        diagnostic_cache_user_compteur()
    except requests.exceptions.ConnectionError:
        print('❌ Erreur: Serveur FastAPI non accessible')
        print('💡 Démarrez le serveur: uvicorn app.main:app --reload')
    except Exception as e:
        print(f'❌ Erreur inattendue: {e}')