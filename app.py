import streamlit as st

# Set page configuration
st.set_page_config(layout="wide", page_title="Getting Started - EuroShield", page_icon="🏢")

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f4788;
        margin-bottom: 1rem;
        text-align: center;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #666;
        margin-bottom: 2rem;
        text-align: center;
    }
    .info-section {
        background-color: #f0f2f6;
        padding: 2rem;
        border-radius: 1rem;
        border-left: 6px solid #1f4788;
        margin: 2rem 0;
    }
    .info-title {
        font-size: 1.5rem;
        font-weight: bold;
        color: #1f4788;
        margin-bottom: 1rem;
    }
    .info-content {
        font-size: 1.1rem;
        line-height: 1.8;
        color: #333;
    }
    .big-button {
        text-align: center;
        margin: 3rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">🏢 EuroShield Insurance Group</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Climate Risk Analytics Platform</div>', unsafe_allow_html=True)

st.markdown("---")

# Company Information Section
st.markdown("""
<div class="info-section">
    <div class="info-title">📋 About EuroShield Insurance Group (ESIG)</div>
    <div class="info-content">
        <p><strong>EuroShield Insurance Group</strong> is a leading European insurance provider committed to protecting individuals and businesses across the continent.</p>
    </div>
</div>
""", unsafe_allow_html=True)

# Geographic Coverage
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    <div class="info-section">
        <div class="info-title">🌍 Geographic Coverage</div>
        <div class="info-content">
            <p>We operate across a comprehensive European market:</p>
            <ul>
                <li><strong>European Union</strong> member states</li>
                <li><strong>United Kingdom</strong></li>
                <li><strong>Norway</strong></li>
                <li><strong>Switzerland</strong></li>
            </ul>
            <p>Our pan-European presence allows us to provide consistent, reliable coverage across diverse markets and regulatory environments.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.html("""
    <div class="info-section">
        <div class="info-title">🏥🏠 Lines of Business</div>
        <div class="info-content">
            <p>This analytics platform focuses on two core insurance products:</p>

            <p><strong>1. Supplemental Health Insurance</strong></p>
            <ul>
                <li>Extra health coverage for individuals</li>
                <li>Employer group health plans</li>
                <li>Comprehensive wellness benefits</li>
            </ul>

            <p><strong>2. Homeowners Insurance</strong></p>
            <ul>
                <li>Buildings and contents coverage</li>
                <li>Flood, windstorm, wildfire, and hail protection</li>
                <li>Standard coverage (earthquake excluded by default in some markets)</li>
            </ul>
        </div>
    </div>
    """)

st.markdown("---")

# Mission Statement
st.markdown("""
<div class="info-section">
    <div class="info-title">🎯 Our Mission</div>
    <div class="info-content">
        <p>At EuroShield, we leverage advanced climate risk analytics to:</p>
        <ul>
            <li><strong>Protect</strong> our policyholders from climate-related disasters</li>
            <li><strong>Anticipate</strong> emerging risks and adapt our coverage accordingly</li>
            <li><strong>Optimize</strong> our portfolio to balance risk and growth</li>
            <li><strong>Innovate</strong> with data-driven insights to improve underwriting decisions</li>
        </ul>
        <p>This dashboard provides comprehensive insights into historical disaster patterns, helping us make informed decisions about risk management, pricing, and market expansion.</p>
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# Big Navigation Button
st.markdown('<div class="big-button">', unsafe_allow_html=True)
col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    if st.button("📊 Go to Portfolio Overview Dashboard", type="primary", width='stretch'):
        st.switch_page("pages/1_Overview.py")
st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("---")
st.caption("""
    🏢 **EuroShield Insurance Group** | Climate Risk Analytics Division  
    Empowering better decisions through data-driven insights
""")