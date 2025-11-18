"""
Script de benchmark pour comparer les performances de logging
Compare le systeme actuel vs le systeme optimise
"""

import time
import statistics
from typing import List, Dict
import sys
import os

# Ajouter le repertoire au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def benchmark_current_logging():
    """Benchmark du systeme de logging actuel"""
    from app.logging_config import init_logging, get_logger, log_api_request

    # Initialiser
    init_logging("production")
    logger = get_logger("app.benchmark")

    times = []

    # Test 1 : Logs simples
    print("\n[CURRENT] Test 1 : Logs simples (1000 iterations)")
    for i in range(1000):
        start = time.time()
        logger.info(f"Test log message {i}")
        times.append((time.time() - start) * 1000000)  # microsecondes

    avg_simple = statistics.mean(times)
    p95_simple = statistics.quantiles(times, n=20)[18]  # P95

    # Test 2 : Logs avec formatage
    times = []
    print("[CURRENT] Test 2 : Logs avec formatage (1000 iterations)")
    for i in range(1000):
        start = time.time()
        logger.info(f"User {i} performed action X at endpoint /api/v1/test with result {i*2}")
        times.append((time.time() - start) * 1000000)

    avg_formatted = statistics.mean(times)
    p95_formatted = statistics.quantiles(times, n=20)[18]

    # Test 3 : Helpers
    times = []
    print("[CURRENT] Test 3 : Helpers (1000 iterations)")
    for i in range(1000):
        start = time.time()
        log_api_request("/api/test", "GET", user_id=i, duration_ms=float(i))
        times.append((time.time() - start) * 1000000)

    avg_helper = statistics.mean(times)
    p95_helper = statistics.quantiles(times, n=20)[18]

    return {
        "simple_avg": avg_simple,
        "simple_p95": p95_simple,
        "formatted_avg": avg_formatted,
        "formatted_p95": p95_formatted,
        "helper_avg": avg_helper,
        "helper_p95": p95_helper,
    }


def benchmark_optimized_logging():
    """Benchmark du systeme de logging optimise"""
    from app.logging_optimized_config import init_optimized_logging, get_optimized_logger

    # Initialiser
    init_optimized_logging("production")
    logger = get_optimized_logger("app.benchmark")

    times = []

    # Test 1 : Logs simples
    print("\n[OPTIMIZED] Test 1 : Logs simples (1000 iterations)")
    for i in range(1000):
        start = time.time()
        logger.info(f"Test log message {i}")
        times.append((time.time() - start) * 1000000)  # microsecondes

    avg_simple = statistics.mean(times)
    p95_simple = statistics.quantiles(times, n=20)[18]  # P95

    # Test 2 : Logs avec formatage
    times = []
    print("[OPTIMIZED] Test 2 : Logs avec formatage (1000 iterations)")
    for i in range(1000):
        start = time.time()
        logger.info(f"User {i} performed action X at endpoint /api/v1/test with result {i*2}")
        times.append((time.time() - start) * 1000000)

    avg_formatted = statistics.mean(times)
    p95_formatted = statistics.quantiles(times, n=20)[18]

    # Test 3 : Logs conditionnels (desactives en production)
    from app.logging_performance_config import should_log_debug

    times = []
    print("[OPTIMIZED] Test 3 : Logs conditionnels (1000 iterations)")
    for i in range(1000):
        start = time.time()
        if should_log_debug():  # False en production
            logger.debug(f"Debug message {i}")
        times.append((time.time() - start) * 1000000)

    avg_conditional = statistics.mean(times)
    p95_conditional = statistics.quantiles(times, n=20)[18]

    return {
        "simple_avg": avg_simple,
        "simple_p95": p95_simple,
        "formatted_avg": avg_formatted,
        "formatted_p95": p95_formatted,
        "conditional_avg": avg_conditional,
        "conditional_p95": p95_conditional,
    }


def print_results(current: Dict, optimized: Dict):
    """Afficher les resultats du benchmark"""
    print("\n" + "=" * 80)
    print("RESULTATS DU BENCHMARK - LOGGING PERFORMANCE")
    print("=" * 80)

    print("\nTest 1 : Logs simples")
    print(f"  Actuel    - Moyenne: {current['simple_avg']:.2f}µs | P95: {current['simple_p95']:.2f}µs")
    print(f"  Optimise  - Moyenne: {optimized['simple_avg']:.2f}µs | P95: {optimized['simple_p95']:.2f}µs")
    improvement_simple = ((current['simple_avg'] - optimized['simple_avg']) / current['simple_avg']) * 100
    print(f"  Gain      - {improvement_simple:+.1f}%")

    print("\nTest 2 : Logs avec formatage")
    print(f"  Actuel    - Moyenne: {current['formatted_avg']:.2f}µs | P95: {current['formatted_p95']:.2f}µs")
    print(f"  Optimise  - Moyenne: {optimized['formatted_avg']:.2f}µs | P95: {optimized['formatted_p95']:.2f}µs")
    improvement_formatted = ((current['formatted_avg'] - optimized['formatted_avg']) / current['formatted_avg']) * 100
    print(f"  Gain      - {improvement_formatted:+.1f}%")

    print("\nTest 3 : Comparaison speciale")
    print(f"  Actuel (Helper)       - Moyenne: {current['helper_avg']:.2f}µs | P95: {current['helper_p95']:.2f}µs")
    print(f"  Optimise (Conditionnel) - Moyenne: {optimized['conditional_avg']:.2f}µs | P95: {optimized['conditional_p95']:.2f}µs")

    # Gain global
    avg_current = (current['simple_avg'] + current['formatted_avg'] + current['helper_avg']) / 3
    avg_optimized = (optimized['simple_avg'] + optimized['formatted_avg'] + optimized['conditional_avg']) / 3
    overall_improvement = ((avg_current - avg_optimized) / avg_current) * 100

    print("\n" + "-" * 80)
    print(f"GAIN GLOBAL MOYEN : {overall_improvement:+.1f}%")
    print("-" * 80)

    # Projection sur une API
    print("\nPROJECTION SUR 10,000 REQUETES/MINUTE :")
    logs_per_request = 5  # Moyenne de logs par requete
    requests_per_min = 10000

    overhead_current = (avg_current * logs_per_request * requests_per_min) / 1000  # ms
    overhead_optimized = (avg_optimized * logs_per_request * requests_per_min) / 1000  # ms

    print(f"  Overhead actuel    : {overhead_current:.0f}ms/min ({overhead_current/60:.1f}ms/sec)")
    print(f"  Overhead optimise  : {overhead_optimized:.0f}ms/min ({overhead_optimized/60:.1f}ms/sec)")
    print(f"  Temps economise    : {overhead_current - overhead_optimized:.0f}ms/min")

    print("\n" + "=" * 80)


def main():
    """Fonction principale"""
    print("=" * 80)
    print("BENCHMARK DES SYSTEMES DE LOGGING")
    print("=" * 80)
    print("\nCe benchmark compare :")
    print("  1. Systeme actuel (app.logging_config)")
    print("  2. Systeme optimise (app.logging_optimized_config)")
    print("\nEnvironnement : PRODUCTION")
    print("Iterations : 1000 par test")

    try:
        # Benchmark systeme actuel
        print("\n" + "-" * 80)
        print("BENCHMARK SYSTEME ACTUEL")
        print("-" * 80)
        current_results = benchmark_current_logging()

        # Petit delai entre les tests
        time.sleep(2)

        # Benchmark systeme optimise
        print("\n" + "-" * 80)
        print("BENCHMARK SYSTEME OPTIMISE")
        print("-" * 80)
        optimized_results = benchmark_optimized_logging()

        # Afficher les resultats
        print_results(current_results, optimized_results)

    except Exception as e:
        print(f"\nERREUR lors du benchmark : {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
