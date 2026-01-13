import streamlit as st
import pandas as pd
from src.expert_scrapers import ExpertScrapers
from src.historical_analyzer import HistoricalAnalyzer
from src.ml_engine import MLDecisionEngine

def render_learning_tab(tab, liga):
    """Renders the Learning & Insights tab"""
    with tab:
        st.header("📚 Machine Learning & Insights")
        
        col_l1, col_l2 = st.columns([2, 1])
        
        with col_l1:
            st.subheader("🎯 Performance del Modelo (ML)")
            
            # Load engine
            ml_engine = MLDecisionEngine()
            insights = ml_engine.get_learning_insights(liga.league_id)
            
            if insights['data_available']:
                # Metrics row
                m1, m2, m3 = st.columns(3)
                m1.metric("Precisión IA", f"{insights['ai_accuracy']:.0%}")
                m2.metric("Decisiones Totales", insights['total_decisions'])
                m3.metric("Éxito Global", f"{insights['overall_success_rate']:.0%}")
                
                st.info("💡 El modelo aprende de tus decisiones y los resultados de los matchups.")
            else:
                st.info("ℹ️ Recopilando datos de decisiones... Necesito más historial para mostrar insights.")
                
            st.subheader("📊 Análisis de Matchups")
            hist_analyzer = HistoricalAnalyzer()
            try:
                perf = hist_analyzer.get_performance_summary(liga.league_id)
                if perf['total_matchups'] > 0:
                    st.dataframe(pd.DataFrame([perf]), use_container_width=True)
                else:
                    st.warning("No hay historial de matchups guardado aún.")
            except:
                st.warning("No se pudo cargar historial.")

        with col_l2:
            st.subheader("🌟 Top Expert Rankings")
            try:
                scraper = ExpertScrapers()
                rankings = scraper.scrape_fantasypros_rankings(limit=50)
                
                top_players = []
                for name, data in list(rankings.items())[:20]:
                    top_players.append({
                        'Rank': data['overall_rank'],
                        'Player': name,
                        'Rating': data['start_sit_rating']
                    })
                
                if top_players:
                    st.dataframe(
                        pd.DataFrame(top_players).set_index('Rank'),
                        use_container_width=True,
                        height=500
                    )
                else:
                    st.warning("No hay rankings disponibles en este momento.")
            except Exception as e:
                st.error(f"Error cargando rankings: {e}")
