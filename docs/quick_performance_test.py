# Test Quick de Performance - Version Simplifié

import requests
import time
import statistics

def quick_performance_test():
    """Test rapide de performance de l'API"""
    
    API_URL = "http://localhost:8001"
    
    # Vérification de connectivité
    print("🔍 Vérification de l'API...")
    try:
        response = requests.get(f"{API_URL}/docs", timeout=5)
        if response.status_code != 200:
            print(f"❌ API non accessible. Status: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Impossible de se connecter à l'API: {e}")
        print("💡 Assurez-vous que l'API tourne sur http://localhost:8001")
        return
    
    print("✅ API accessible!")
    
    # Tests simples
    endpoints = [
        "/user/",
        "/user/1", 
        "/user/phonenumber/773234567/exist"
    ]
    
    print(f"\n🧪 Test de {len(endpoints)} endpoints (10 requêtes chacun)")
    
    all_times = []
    
    for endpoint in endpoints:
        print(f"\n📊 Test {endpoint}")
        times = []
        
        for i in range(10):
            start = time.time()
            try:
                response = requests.get(f"{API_URL}{endpoint}")
                end = time.time()
                
                response_time = (end - start) * 1000  # en ms
                times.append(response_time)
                
                status = "✅" if response.status_code == 200 else "⚠️"
                print(f"   {i+1}/10: {response_time:.2f}ms {status}")
                
            except Exception as e:
                print(f"   {i+1}/10: ERROR - {e}")
        
        if times:
            avg_time = statistics.mean(times)
            min_time = min(times)
            max_time = max(times)
            
            print(f"   📈 Moyenne: {avg_time:.2f}ms | Min: {min_time:.2f}ms | Max: {max_time:.2f}ms")
            all_times.extend(times)
        else:
            print("   ❌ Aucune réponse valide")
    
    # Résumé global
    if all_times:
        overall_avg = statistics.mean(all_times)
        print(f"\n🎯 RÉSUMÉ GLOBAL:")
        print(f"   Temps moyen: {overall_avg:.2f}ms")
        print(f"   Temps min: {min(all_times):.2f}ms") 
        print(f"   Temps max: {max(all_times):.2f}ms")
        
        # Évaluation
        if overall_avg < 50:
            print("   🚀 Performance EXCELLENTE (< 50ms)")
        elif overall_avg < 100:
            print("   ✅ Performance BONNE (< 100ms)")
        elif overall_avg < 200:
            print("   ⚠️ Performance ACCEPTABLE (< 200ms)")
        else:
            print("   🐌 Performance À AMÉLIORER (> 200ms)")
        
        # Analyse logging overhead
        print(f"\n🔍 ANALYSE OVERHEAD LOGGING:")
        baseline_expected = 15  # ms sans logging estimé
        
        if overall_avg <= baseline_expected * 1.2:  # +20%
            print("   ✅ Overhead logging NÉGLIGEABLE (<20%)")
            print("   ✅ Vous pouvez continuer l'intégration complète")
        elif overall_avg <= baseline_expected * 1.5:  # +50%
            print("   ⚠️ Overhead logging MODÉRÉ (20-50%)")
            print("   💡 Considérez la config production optimisée")
        else:
            print("   ❌ Overhead logging ÉLEVÉ (>50%)")
            print("   🔧 Activez logging_performance_config.py")

if __name__ == "__main__":
    print("⚡ Test Rapide de Performance - SamaConso API")
    print("=" * 50)
    quick_performance_test()