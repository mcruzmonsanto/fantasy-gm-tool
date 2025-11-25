import sys
import os
import pprint # Para imprimir ordenado

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.conectar import obtener_liga
from config.credenciales import LIGAS

def inspeccionar():
    # Usamos la primera liga
    nombre = list(LIGAS.keys())[0]
    liga = obtener_liga(nombre)
    
    print(f"\n🕵️ INSPECCIONANDO UN JUGADOR LIBRE EN {nombre}...")
    
    # Traemos 1 solo jugador libre
    agentes = liga.free_agents(size=1)
    
    if agentes:
        jugador = agentes[0]
        print(f"Nombre: {jugador.name}")
        print("--- LISTA DE ATRIBUTOS (ADN) ---")
        
        # Esto imprime TODAS las variables que tiene el objeto jugador
        pprint.pprint(jugador.__dict__)
        
        print("-" * 40)
        print("Busca algo como 'status', 'acquisitionStatus', 'availability'...")
    else:
        print("No hay agentes libres para inspeccionar.")

if __name__ == "__main__":
    inspeccionar()