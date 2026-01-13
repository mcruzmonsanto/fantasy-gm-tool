"""Panel de diagnóstico para debugging"""
import streamlit as st
import requests
from datetime import datetime
import pytz

def show_diagnostic_panel():
    """Muestra panel de diagnóstico en sidebar"""
    with st.sidebar.expander("🔧 Diagnóstico", expanded=False):
        st.caption("**Sistema**")
        
        # Check ESPN API
        try:
            r = requests.get(
                "http://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
                timeout=3
            )
            api_status = "🟢 Online" if r.status_code == 200 else "🔴 Error"
        except:
            api_status = "🔴 No disponible"
        
        st.caption(f"ESPN API: {api_status}")
        
        # Timezone check
        tz = pytz.timezone('US/Eastern')
        now_et = datetime.now(tz)
        st.caption(f"Hora ET: {now_et.strftime('%H:%M:%S')}")
        
        # Cache stats
        cache_stats = st.session_state.get('cache_stats', {})
        if cache_stats:
            st.caption(f"Cache hits: {cache_stats.get('hits', 0)}")
            st.caption(f"Cache misses: {cache_stats.get('misses', 0)}")
        
        # Botón de reset completo
        if st.button("🔄 Reset Total", type="secondary"):
            st.cache_data.clear()
            st.session_state.clear()
            st.rerun()
