# app.py
import streamlit as st
import pandas as pd
from datetime import date, datetime
from io import BytesIO
import os
import importlib.util
import json
import sqlite3
from pathlib import Path

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOGIC_MODULE_DIR = os.path.join(APP_DIR, "logic_modules")

# Database configuration for persistent storage
DB_PATH = Path.home() / ".streamlit" / "test_data_generator_configs.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def init_database():
    """Initialize SQLite database for persistent configuration storage"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS configurations (
                config_name TEXT PRIMARY KEY,
                config_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Database initialization error: {e}")
        return False

# Initialize database on app start
init_database()

# --- Configuration Management Functions ---
def save_configuration(config_name, config_data):
    """Save configuration to SQLite database"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        config_json = json.dumps(config_data)

        # Use INSERT OR REPLACE to handle updates
        cursor.execute('''
            INSERT OR REPLACE INTO configurations (config_name, config_data, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (config_name, config_json))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error saving configuration: {e}")
        return False

def load_configuration(config_name):
    """Load configuration from SQLite database"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT config_data FROM configurations WHERE config_name = ?
        ''', (config_name,))

        result = cursor.fetchone()
        conn.close()

        if result:
            return json.loads(result[0])
        return None
    except Exception as e:
        st.error(f"Error loading configuration: {e}")
        return None

def get_saved_configurations():
    """Get list of saved configuration names from database"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT config_name FROM configurations ORDER BY updated_at DESC
        ''')

        configs = [row[0] for row in cursor.fetchall()]
        conn.close()
        return configs
    except Exception:
        return []

def delete_configuration(config_name):
    """Delete a saved configuration from database"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        cursor.execute('''
            DELETE FROM configurations WHERE config_name = ?
        ''', (config_name,))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error deleting configuration: {e}")
        return False

def export_all_configurations():
    """Export all configurations as a JSON file for backup"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        cursor.execute('SELECT config_name, config_data FROM configurations')
        all_configs = {row[0]: json.loads(row[1]) for row in cursor.fetchall()}

        conn.close()
        return json.dumps(all_configs, indent=2)
    except Exception as e:
        st.error(f"Error exporting configurations: {e}")
        return None

def import_configurations(json_data):
    """Import configurations from JSON backup"""
    try:
        configs = json.loads(json_data)
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()

        for config_name, config_data in configs.items():
            config_json = json.dumps(config_data)
            cursor.execute('''
                INSERT OR REPLACE INTO configurations (config_name, config_data, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (config_name, config_json))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Error importing configurations: {e}")
        return False

def collect_current_config():
    """Collect current UI state into a configuration dictionary"""
    config = {
        'product_display_name': st.session_state.get('product_display_name_input', ''),
        'product_code': st.session_state.get('product_code_input', ''),
        'count_mode': st.session_state.get('count_mode_selector', 'Apply Same Count to All Epics'),
        'ui_state': {}
    }

    # Collect all relevant session state keys
    for key, value in st.session_state.items():
        if any(key.startswith(prefix) for prefix in [
            'epic_cb_', 'epic_pos_', 'epic_neg_', 'ppt_enabled_',
            'entry_age_slider_', 'maturity_age_slider_', 'freq_cb_',
            'sa_enabled_', 'min_sp_', 'max_sp_', 'pos_sp_', 'neg_sp_',
            'min_oth_', 'max_oth_', 'pos_oth_', 'neg_oth_',
            'select_all_epics_master'
        ]):
            # Convert non-serializable types
            if isinstance(value, (int, float, str, bool, list, dict, type(None))):
                config['ui_state'][key] = value
            elif isinstance(value, tuple):
                config['ui_state'][key] = list(value)

    return config

def apply_config_to_ui(config):
    """Apply saved configuration to UI state"""
    # Apply product info
    if 'product_display_name' in config:
        st.session_state['product_display_name_input'] = config['product_display_name']
    if 'product_code' in config:
        st.session_state['product_code_input'] = config['product_code']
    if 'count_mode' in config:
        st.session_state['count_mode_selector'] = config['count_mode']

    # Apply UI state
    if 'ui_state' in config:
        for key, value in config['ui_state'].items():
            # Convert lists back to tuples for sliders
            if 'slider' in key and isinstance(value, list) and len(value) == 2:
                st.session_state[key] = tuple(value)
            else:
                st.session_state[key] = value

# --- All helper functions (display_generation_summary, etc.) remain unchanged ---
def display_generation_summary(df_results):
    st.subheader("📊 Generation Summary")
    total_cases_summary = len(df_results)

    positive_cases = 0
    negative_cases = 0
    if 'Test_Type' in df_results.columns:
        test_type_counts = df_results['Test_Type'].value_counts()
        positive_cases = test_type_counts.get('Positive', 0)
        negative_cases = test_type_counts.get('Negative', 0)

    col_sum1, col_sum2, col_sum3 = st.columns(3)
    col_sum1.metric("Total Cases", total_cases_summary)
    col_sum2.metric("✔️ Positive Cases", positive_cases)
    col_sum3.metric("❌ Negative Cases", negative_cases)

    if 'Epic' in df_results.columns:
        epic_counts = df_results['Epic'].value_counts()
        with st.expander("Case Distribution by Epic", expanded=False):
            if not epic_counts.empty:
                st.bar_chart(epic_counts)
            else:
                st.caption("No Epic data to display or 'Epic' column missing.")

def highlight_rule_outcomes(s):
    def get_style(val_str):
        if 'Fail' in val_str:
            return 'background-color: #FFE0E0; color: #A00000;'
        elif val_str == 'Pass':
            return 'background-color: #E0FFE0; color: #006000;'
        return ''
    return [get_style(str(v)) for v in s]

def get_available_logic_modules():
    modules = {}
    if not os.path.exists(LOGIC_MODULE_DIR):
        return modules
    try:
        for filename in os.listdir(LOGIC_MODULE_DIR):
            if filename.endswith(".py") and not filename.startswith("__"):
                module_name_py_file = filename[:-3]
                try:
                    spec = importlib.util.spec_from_file_location(module_name_py_file, os.path.join(LOGIC_MODULE_DIR, filename))
                    module_obj = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module_obj)
                    display_name = getattr(module_obj, 'MODULE_NAME', module_name_py_file.replace("_", " ").title())
                    modules[display_name] = module_name_py_file
                except Exception:
                    modules[module_name_py_file.replace("_", " ").title()] = module_name_py_file
    except Exception as e:
        st.sidebar.error(f"Error listing logic modules: {e}")
    return modules

def load_logic_module(module_name_py, override_display_name=None, override_product_code=None):
    """
    Load the logic module and optionally override its MODULE_NAME and PRODUCT_CODE
    with values provided from the UI.
    """
    try:
        module_path = os.path.join(LOGIC_MODULE_DIR, f"{module_name_py}.py")
        spec = importlib.util.spec_from_file_location(module_name_py, module_path)
        logic_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(logic_module)
        # Apply overrides if provided
        try:
            if override_display_name:
                setattr(logic_module, 'MODULE_NAME', override_display_name)
            if override_product_code:
                setattr(logic_module, 'PRODUCT_CODE', override_product_code)
        except Exception:
            pass
        return logic_module
    except Exception as e:
        st.error(f"Error loading logic module '{module_name_py}': {e}")
        st.exception(e)
        return None


# --- Streamlit App UI ---
st.set_page_config(
    page_title="Test Data Generator",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)
# Hide Streamlit's default menu and footer
hide_streamlit_style = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)
# Inject custom CSS
st.markdown("""
    <style>
    .custom-title {
        font-size:40px !important;
        font-weight: bold;
        color: #2E86C1;
    }
    </style>
    """, unsafe_allow_html=True)

# Use the custom class
st.markdown('<h1 class="custom-title">⚙️ Product Rule Validation Test Data Generator</h1>', unsafe_allow_html=True)

# --- Session State Initialization ---
if 'generated_df' not in st.session_state: st.session_state.generated_df = None
if 'selected_module_name_py' not in st.session_state: st.session_state.selected_module_name_py = None
if 'selected_display_name' not in st.session_state: st.session_state.selected_display_name = None
if 'processing' not in st.session_state: st.session_state.processing = False
if 'epic_counts_to_generate' not in st.session_state: st.session_state.epic_counts_to_generate = {}
if 'epic_counts_to_generate_rider' not in st.session_state: st.session_state.epic_counts_to_generate_rider = {}
if 'config_loaded' not in st.session_state: st.session_state.config_loaded = False


# --- Sidebar Configuration ---
with st.sidebar:
    st.header("🛠️ Configuration Management")

    # Configuration Save/Load Section
    with st.expander("💾 Save/Load Configurations", expanded=False):
        # Save Configuration
        st.subheader("Save Current Configuration")
        save_config_name = st.text_input("Configuration Name", key="save_config_name_input")
        if st.button("💾 Save Configuration", use_container_width=True):
            if save_config_name:
                config = collect_current_config()
                if save_configuration(save_config_name, config):
                    st.success(f"✅ Configuration '{save_config_name}' saved successfully!")
                    st.rerun()
            else:
                st.warning("Please enter a configuration name")

        st.divider()

        # Load Configuration
        st.subheader("Load Saved Configuration")
        saved_configs = get_saved_configurations()
        if saved_configs:
            selected_config = st.selectbox("Select Configuration", saved_configs, key="load_config_select")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("📂 Load", use_container_width=True):
                    config = load_configuration(selected_config)
                    if config:
                        apply_config_to_ui(config)
                        st.session_state.config_loaded = True
                        st.success(f"✅ Configuration '{selected_config}' loaded!")
                        st.rerun()

            with col2:
                if st.button("🗑️ Delete", use_container_width=True):
                    if delete_configuration(selected_config):
                        st.success(f"✅ Configuration '{selected_config}' deleted!")
                        st.rerun()
        else:
            st.info("No saved configurations found")

        # st.divider()

        # Backup/Restore Section
        # st.subheader("Backup & Restore")

        # col_backup1, col_backup2 = st.columns(2)

        # with col_backup1:
        #     # Export configurations
        #     if st.button("📤 Export All", use_container_width=True, help="Download all configurations as JSON"):
        #         export_data = export_all_configurations()
        #         if export_data:
        #             st.download_button(
        #                 label="⬇️ Download Backup",
        #                 data=export_data,
        #                 file_name=f"configs_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        #                 mime="application/json",
        #                 use_container_width=True
        #             )

        # with col_backup2:
        #     # Import configurations
        #     uploaded_file = st.file_uploader("📥 Import Backup", type=['json'], key="import_configs", label_visibility="collapsed")
        #     if uploaded_file is not None:
        #         try:
        #             import_data = uploaded_file.read().decode('utf-8')
        #             if import_configurations(import_data):
        #                 st.success("✅ Configurations imported successfully!")
        #                 st.rerun()
        #         except Exception as e:
        #             st.error(f"Import failed: {e}")

    # st.divider()

    # There is only one logic module now. Discover it and then
    # accept product display name and product code from the user.
    available_modules = get_available_logic_modules()
    if not available_modules:
        st.error(f"Logic module directory ('{LOGIC_MODULE_DIR}') not found or empty.")
        st.stop()

    # pick the first (and only) module file
    first_display_name, first_module_py = next(iter(available_modules.items()))

    # Initialize session defaults if missing
    if 'product_display_name_input' not in st.session_state:
        st.session_state['product_display_name_input'] = first_display_name
    if 'product_code_input' not in st.session_state:
        # prefer any existing stored code, else empty
        st.session_state['product_code_input'] = st.session_state.get('product_code', '') or ''
    if 'selected_module_name_py' not in st.session_state:
        st.session_state['selected_module_name_py'] = first_module_py

    # Let user type a display name and a product code
    st.markdown("""
        <style>
        input[type="text"] {
            font-size: 20px !important;
        }
        </style>
        """, unsafe_allow_html=True)

    # Your input fields
    st.text_input("Product display name", key='product_display_name_input')
    st.text_input("Product code", key='product_code_input')

    # mirror to commonly used session keys for backward compatibility
    st.session_state['selected_display_name'] = st.session_state.get('product_display_name_input')
    st.session_state['product_code'] = st.session_state.get('product_code_input')
    # ensure the module pointer remains the discovered module
    st.session_state['selected_module_name_py'] = first_module_py

    # st.divider()
    st.header("Configure Case Counts")

    # --- START OF CHANGE: Added Radio button for count mode ---
    count_mode = st.radio(
        "Select Count Mode:",
        options=["Apply Same Count to All Epics", "Set Individual Counts for Each Epic"],
        index=0,
        key="count_mode_selector"
    )

    num_positive_global, num_negative_global = 5, 5
    if count_mode == "Apply Same Count to All Epics":
        col1, col2 = st.columns(2)
        with col1:
            num_positive_global = st.number_input("Positive Cases", min_value=0, value=5)
        with col2:
            num_negative_global = st.number_input("Negative Cases", min_value=0, value=5)
    # --- END OF CHANGE ---

# --- Epic and Case Count Selection on Main Canvas ---
epic_counts = {}
selected_epics = []

epic_counts_rider = {}
selected_epics_rider = []

if st.session_state.selected_module_name_py and st.session_state.generated_df is None:
    st.markdown("""
                <style>
                /* Make sure all descendant text elements inherit the size */
                div[data-testid="stExpander"] button * ,
                div[data-testid="stExpander"] summary * ,
                div[data-testid="stExpander"] [role="button"] * {
                    font-size: 16px !important;
                    font-weight: 600 !important;
                }
            """, unsafe_allow_html=True)

    tab3a, tab3b = st.tabs(["Base Plan Epics", "Rider Epics"])
    with tab3a:
        # st.header("Base Plan Epics")
        logic_module = load_logic_module(
            st.session_state.selected_module_name_py,
            override_display_name=st.session_state.get('product_display_name_input'),
            override_product_code=st.session_state.get('product_code_input')
        )
        if logic_module and hasattr(logic_module, 'EPIC_MAP'):

            epic_map = getattr(logic_module, 'EPIC_MAP')
            select_all = st.checkbox("Select/Deselect All Epics", value=True, key='select_all_epics_master')
            # st.markdown("#### Configure Epics and Case Counts")
            # st.markdown("---")
            with st.expander("ℹ️ Configure Epics and Case Counts", expanded=True):
                ppt_names = ["Single Pay", "Limited Pay (5 pay)", "Limited Pay (10 pay)", "Limited Pay (15 pay)", "Limited Pay (Pay till age 60)", "Regular Pay"]

                for epic_key, epic_desc in epic_map.items():
                    toggle_key = None
                    ppt_names = ["Single Pay", "Limited Pay (5 pay)", "Limited Pay (10 pay)", "Limited Pay (15 pay)", "Limited Pay (Pay till age 60)", "Regular Pay"]
                    entry_age_ppt_ranges = {
                        "Single Pay": (18, 65),
                        "Limited Pay (5 pay)": (18, 65),
                        "Limited Pay (10 pay)": (18, 65),
                        "Limited Pay (15 pay)": (18, 65),
                        "Limited Pay (Pay till age 60)": (18, 55),
                        "Regular Pay": (18, 65)
                    }
                    policy_term_ppt_ranges = {
                        "Single Pay": (1, 5),
                        "Limited Pay (5 pay)": (10, 67),
                        "Limited Pay (10 pay)": (15, 67),
                        "Limited Pay (15 pay)": (20, 67),
                        "Limited Pay (Pay till age 60)": (5, 67),
                        "Regular Pay": (5, 67)
                    }
                    maturity_age_ppt_ranges = {
                        "Single Pay": (19, 85),
                        "Limited Pay (5 pay)": (24, 85),
                        "Limited Pay (10 pay)": (29, 85),
                        "Limited Pay (15 pay)": (34, 85),
                        "Limited Pay (Pay till age 60)": (65, 85),
                        "Regular Pay": (23, 85)
                    }
                    premium_paying_ppt_ranges = {
                        "Single Pay": (1, 1),
                        "Limited Pay (5 pay)": (5, 5),
                        "Limited Pay (10 pay)": (10, 10),
                        "Limited Pay (15 pay)": (15, 15),
                        "Limited Pay (Pay till age 60)": (5, 42),
                        "Regular Pay": (5, 67)
                    }
                    sum_assured_ranges = {
                        "Single Pay": (2500000, 5000000),
                        "Others": (5000000, 20000000),
                    }

                    if count_mode == "Set Individual Counts for Each Epic":
                        if epic_key == "EntryAge" or epic_key == "PremiumPayingTerm" or epic_key == "PolicyTerm" or epic_key == "MaturityAge":

                            is_selected = st.checkbox(epic_desc, value=select_all, key=f"epic_cb_{epic_key}")
                            with st.expander("Show/Hide PPT Configuration", expanded=False):
                                ppt_age_ranges, ppt_pos_counts, ppt_neg_counts, ppt_enabled = {}, {}, {}, {}

                                header = st.columns([0.5, 2, 2, 1, 1])
                                # with header[0]: st.markdown("**Enable**")
                                with header[1]: st.markdown("**PPT Name**")
                                with header[2]: st.markdown("**Min/Max**")
                                with header[3]: st.markdown("**Pos**")
                                with header[4]: st.markdown("**Neg**")

                                for ppt in ppt_names:
                                    row = st.columns([0.5, 2, 2, 1, 1])
                                    with row[0]:
                                        enabled = st.checkbox("Enable", value=is_selected, key=f"ppt_enabled_{epic_key}_{ppt}", label_visibility="collapsed")
                                    with row[1]: st.markdown(ppt)
                                    with row[2]:
                                        if(epic_key == "EntryAge"):
                                            min_age, max_age = st.slider("Entry Age", 0, 85, entry_age_ppt_ranges[ppt], key=f"entry_age_slider_{epic_key}_{ppt}",
                                                                    label_visibility="collapsed")
                                        elif(epic_key == "PolicyTerm"):
                                                min_age, max_age = st.slider("Policy Term", 5, 80, policy_term_ppt_ranges[ppt], key=f"entry_age_slider_{epic_key}_{ppt}",
                                                                    label_visibility="collapsed")
                                        elif(epic_key == "MaturityAge"):
                                            min_age, max_age = st.slider("Maturity Age", 19, 85, maturity_age_ppt_ranges[ppt], key=f"maturity_age_slider_{epic_key}_{ppt}",
                                                                    label_visibility="collapsed")
                                        else:
                                            if(premium_paying_ppt_ranges[ppt][0] == premium_paying_ppt_ranges[ppt][1]):
                                                min_age = max_age = st.slider("Entry Age", 0, 85, premium_paying_ppt_ranges[ppt][0], key=f"entry_age_slider_{epic_key}_{ppt}", label_visibility="collapsed")
                                            else:
                                                min_age, max_age = st.slider("Entry Age", 0, 85, premium_paying_ppt_ranges[ppt], key=f"entry_age_slider_{epic_key}_{ppt}",
                                                                    label_visibility="collapsed")
                                    with row[3]:
                                        pos = st.number_input("Pos", 0, value=5, key=f"epic_pos_{epic_key}_{ppt}", label_visibility="collapsed")
                                    with row[4]:
                                        neg = st.number_input("Neg", 0, value=5, key=f"epic_neg_{epic_key}_{ppt}", label_visibility="collapsed")

                                    if enabled:
                                        ppt_age_ranges[ppt] = (min_age, max_age)
                                        ppt_pos_counts[ppt] = pos
                                        ppt_neg_counts[ppt] = neg
                                        ppt_enabled[ppt] = True
                                    else:
                                        ppt_enabled[ppt] = False

                                if is_selected and any(ppt_enabled.values()):
                                    selected_epics.append(epic_key)
                                    epic_counts[epic_key] = {
                                        "ppt_age_ranges": ppt_age_ranges,
                                        "ppt_pos_counts": ppt_pos_counts,
                                        "ppt_neg_counts": ppt_neg_counts,
                                        "ppt_enabled": ppt_enabled
                                    }

                        elif epic_key == "PaymentFrequency":
                            row = st.columns([2, 1.5, 1.5])
                            with row[0]:
                                is_selected = st.checkbox(epic_desc, value=select_all, key=f"epic_cb_{epic_key}")
                            with row[1]:
                                pos_count = st.number_input(f"Pos {epic_key}", min_value=0, value=5, key=f"epic_pos_{epic_key}", label_visibility="collapsed", placeholder="Pos")
                            with row[2]:
                                neg_count = st.number_input(f"Neg {epic_key}", min_value=0, value=5, key=f"epic_neg_{epic_key}", label_visibility="collapsed", placeholder="Neg")

                            frequency_options = ["Annual", "Half-Yearly", "Quarterly", "Monthly", "Single Pay"]
                            frequency_map = {"Annual": 1, "Half-Yearly": 2, "Quarterly": 3, "Monthly": 4, "Single Pay": 5}
                            freq_cols = st.columns(len(frequency_options)+1)
                            selected_frequencies = []
                            for i, freq in enumerate(frequency_options):
                                with freq_cols[i+1]:
                                    if st.checkbox(freq, value=is_selected, key=f"freq_cb_{freq}"):
                                        selected_frequencies.append(freq)

                            mapped_frequencies = [frequency_map[f] for f in selected_frequencies]

                            if is_selected:
                                selected_epics.append(epic_key)
                                epic_counts[epic_key] = {
                                    "positive": pos_count,
                                    "negative": neg_count,
                                    "payment_frequency_options": mapped_frequencies
                                }

                        elif epic_key == "SumAssuredValidation":
                            is_selected = st.checkbox(epic_desc, value=select_all, key=f"epic_cb_{epic_key}")
                            with st.expander("Show/Hide PPT Configuration", expanded=False):

                                header = st.columns([0.5, 2, 1, 1, 1, 1])
                                # with header[0]: st.markdown("**Enable**")
                                with header[1]: st.markdown("**PPT Type**")
                                with header[2]: st.markdown("**Min**")
                                with header[3]: st.markdown("**Max**")
                                with header[4]: st.markdown("**Pos**")
                                with header[5]: st.markdown("**Neg**")

                                row_sp = st.columns([0.5, 2, 1, 1, 1, 1])
                                with row_sp[0]:
                                    sp = st.checkbox("Enable", value=is_selected, key=f"sa_enabled_{epic_key}", label_visibility="collapsed")
                                with row_sp[1]:
                                    st.markdown("SinglePay")
                                with row_sp[2]:
                                    min_sp = st.number_input("Min SinglePay", min_value=0, value=sum_assured_ranges["Single Pay"][0], key=f"min_sp_{epic_key}", label_visibility="collapsed")
                                with row_sp[3]:
                                    max_sp = st.number_input("Max SinglePay", min_value=min_sp, value=sum_assured_ranges["Single Pay"][1], key=f"max_sp_{epic_key}", label_visibility="collapsed")
                                with row_sp[4]:
                                    pos_sp = st.number_input("Pos SinglePay", min_value=0, value=5, key=f"pos_sp_{epic_key}", label_visibility="collapsed")
                                with row_sp[5]:
                                    neg_sp = st.number_input("Neg SinglePay", min_value=0, value=5, key=f"neg_sp_{epic_key}", label_visibility="collapsed")

                                row_oth = st.columns([0.5, 2, 1, 1, 1, 1])
                                with row_oth[0]:
                                    oth = st.checkbox("Enable", value=is_selected, key=f"oth_enabled_{epic_key}", label_visibility="collapsed")
                                with row_oth[1]:
                                    st.markdown("Others")
                                with row_oth[2]:
                                    min_oth = st.number_input("Min Others", min_value=0, value=sum_assured_ranges["Others"][0], key=f"min_oth_{epic_key}", label_visibility="collapsed")
                                with row_oth[3]:
                                    max_oth = st.number_input("Max Others", min_value=min_oth, value=sum_assured_ranges["Others"][1], key=f"max_oth_{epic_key}", label_visibility="collapsed")
                                with row_oth[4]:
                                    pos_oth = st.number_input("Pos Others", min_value=0, value=5, key=f"pos_oth_{epic_key}", label_visibility="collapsed")
                                with row_oth[5]:
                                    neg_oth = st.number_input("Neg Others", min_value=0, value=5, key=f"neg_oth_{epic_key}", label_visibility="collapsed")

                                if is_selected:
                                    selected_epics.append(epic_key)
                                    if epic_key not in epic_counts:
                                        epic_counts[epic_key] = {}
                                    if sp:
                                        epic_counts[epic_key]["Single Pay"] = {
                                            "min_val": min_sp,
                                            "max_val": max_sp,
                                            "positive": num_positive_global,
                                            "negative": num_negative_global
                                        }
                                    if oth:
                                        epic_counts[epic_key]["Others"] = {
                                            "min_val": min_oth,
                                            "max_val": max_oth,
                                            "positive": num_positive_global,
                                            "negative": num_negative_global
                                        }

                        else:
                            # For other epics, use slider for min/max and number inputs for pos/neg
                            row = st.columns([2, 1.5, 1.5])
                            with row[0]:
                                is_selected = st.checkbox(epic_desc, value=select_all, key=f"epic_cb_{epic_key}")
                            with row[1]:
                                pos_count = st.number_input(f"Pos {epic_key}", min_value=0, value=5, key=f"epic_pos_{epic_key}", label_visibility="collapsed", placeholder="Pos")
                            with row[2]:
                                neg_count = st.number_input(f"Neg {epic_key}", min_value=0, value=5, key=f"epic_neg_{epic_key}", label_visibility="collapsed", placeholder="Neg")
                            if is_selected:
                                selected_epics.append(epic_key)
                                epic_counts[epic_key] = {
                                    "positive": pos_count,
                                    "negative": neg_count
                                }

                    else:  # Apply Same Count to All Epics
                        if epic_key == "EntryAge" or epic_key == "PremiumPayingTerm" or epic_key == "PolicyTerm" or epic_key == "MaturityAge":

                            is_selected = st.checkbox(epic_desc, value=select_all, key=f"epic_cb_{epic_key}")
                            with st.expander("Show/Hide PPT Configuration", expanded=False):
                                ppt_age_ranges, ppt_enabled = {}, {}

                                for ppt in ppt_names:
                                    row = st.columns([0.5, 2, 2])
                                    with row[0]:
                                        enabled = st.checkbox("Enable", value=is_selected, key=f"ppt_enabled_all_{epic_key}_{ppt}", label_visibility="collapsed")
                                    with row[1]: st.markdown(ppt)
                                    with row[2]:
                                        if(epic_key == "EntryAge"):
                                            min_age, max_age = st.slider("Entry Age", 0, 85, entry_age_ppt_ranges[ppt], key=f"entry_age_slider_{epic_key}_{ppt}",
                                                                    label_visibility="collapsed")
                                        elif(epic_key == "PolicyTerm"):
                                            min_age, max_age = st.slider("Policy Term", 5, 80, policy_term_ppt_ranges[ppt], key=f"entry_age_slider_{epic_key}_{ppt}",
                                                                    label_visibility="collapsed")
                                        elif(epic_key == "MaturityAge"):
                                            min_age, max_age = st.slider("Maturity Age", 19, 85, maturity_age_ppt_ranges[ppt], key=f"maturity_age_slider_{epic_key}_{ppt}",
                                                                    label_visibility="collapsed")
                                        else:
                                            if(premium_paying_ppt_ranges[ppt][0] == premium_paying_ppt_ranges[ppt][1]):
                                                min_age = max_age = st.slider("Entry Age", 0, 85, premium_paying_ppt_ranges[ppt][0], key=f"entry_age_slider_{epic_key}_{ppt}", label_visibility="collapsed")
                                            else:
                                                min_age, max_age = st.slider("Entry Age", 0, 85, premium_paying_ppt_ranges[ppt], key=f"entry_age_slider_{epic_key}_{ppt}",
                                                                    label_visibility="collapsed")
                                    if enabled:
                                        ppt_age_ranges[ppt] = (min_age, max_age)
                                        ppt_enabled[ppt] = True
                                    else:
                                        ppt_enabled[ppt] = False

                                if is_selected and any(ppt_enabled.values()):
                                    selected_epics.append(epic_key)
                                    epic_counts[epic_key] = {
                                        "ppt_age_ranges": ppt_age_ranges,
                                        "ppt_enabled": ppt_enabled,
                                        "positive": num_positive_global,
                                        "negative": num_negative_global
                                    }

                        elif epic_key == "PaymentFrequency":
                            is_selected = st.checkbox(epic_desc, value=select_all, key=f"epic_cb_{epic_key}")
                            frequency_options = ["Annual", "Half-Yearly", "Quarterly", "Monthly", "Single Pay"]
                            frequency_map = {"Annual": 1, "Half-Yearly": 2, "Quarterly": 3, "Monthly": 4, "Single Pay": 5}
                            freq_cols = st.columns(len(frequency_options)+1)
                            selected_frequencies = []
                            for i, freq in enumerate(frequency_options):
                                with freq_cols[i+1]:
                                    if st.checkbox(freq, value=is_selected, key=f"freq_cb_{freq}"):
                                        selected_frequencies.append(freq)

                            mapped_frequencies = [frequency_map[f] for f in selected_frequencies]

                            if is_selected:
                                selected_epics.append(epic_key)
                                epic_counts[epic_key] = {
                                    "positive": num_positive_global,
                                    "negative": num_negative_global,
                                    "payment_frequency_options": mapped_frequencies
                                }

                        elif epic_key == "SumAssuredValidation":
                            is_selected = st.checkbox(epic_desc, value=select_all, key=f"epic_cb_{epic_key}")
                            with st.expander("Show/Hide PPT Configuration", expanded=False):

                                header = st.columns([0.5, 2, 1, 1])
                                # with header[0]: st.markdown("**Enable**")
                                with header[1]: st.markdown("**PPT Type**")
                                with header[2]: st.markdown("**Min**")
                                with header[3]: st.markdown("**Max**")

                                row_sp = st.columns([0.5, 2, 1, 1])
                                with row_sp[0]:
                                    sp = st.checkbox("Enable", value=is_selected, key=f"sa_enabled_{epic_key}", label_visibility="collapsed")
                                with row_sp[1]:
                                    st.markdown("SinglePay")
                                with row_sp[2]:
                                    min_sp = st.number_input("Min SinglePay", min_value=0, value=sum_assured_ranges["Single Pay"][0], key=f"min_sp_{epic_key}", label_visibility="collapsed")
                                with row_sp[3]:
                                    max_sp = st.number_input("Max SinglePay", min_value=min_sp, value=sum_assured_ranges["Single Pay"][1], key=f"max_sp_{epic_key}", label_visibility="collapsed")

                                row_oth = st.columns([0.5, 2, 1, 1])
                                with row_oth[0]:
                                    oth = st.checkbox("Enable", value=is_selected, key=f"oth_enabled_{epic_key}", label_visibility="collapsed")
                                with row_oth[1]:
                                    st.markdown("Others")
                                with row_oth[2]:
                                    min_oth = st.number_input("Min Others", min_value=0, value=sum_assured_ranges["Others"][0], key=f"min_oth_{epic_key}", label_visibility="collapsed")
                                with row_oth[3]:
                                    max_oth = st.number_input("Max Others", min_value=min_oth, value=sum_assured_ranges["Others"][1], key=f"max_oth_{epic_key}", label_visibility="collapsed")

                                if is_selected:
                                    selected_epics.append(epic_key)
                                    if epic_key not in epic_counts:
                                        epic_counts[epic_key] = {}
                                    if sp:
                                        epic_counts[epic_key]["Single Pay"] = {
                                            "min_val": min_sp,
                                            "max_val": max_sp,
                                            "positive": num_positive_global,
                                            "negative": num_negative_global
                                        }
                                    if oth:
                                        epic_counts[epic_key]["Others"] = {
                                            "min_val": min_oth,
                                            "max_val": max_oth,
                                            "positive": num_positive_global,
                                            "negative": num_negative_global
                                        }

                        else:
                            is_selected = st.checkbox(epic_desc, value=select_all, key=f"epic_cb_{epic_key}")
                            if is_selected:
                                selected_epics.append(epic_key)
                                epic_counts[epic_key] = {"positive": num_positive_global, "negative": num_negative_global}

                # print(epic_counts)
            # print("Epics Selected:", selected_epics, "\n")

    # For added riders if any
    with tab3b:
        # st.header("Rider Epics")
        logic_module = load_logic_module(
            st.session_state.selected_module_name_py,
            override_display_name=st.session_state.get('product_display_name_input'),
            override_product_code=st.session_state.get('product_code_input')
        )
        if logic_module and hasattr(logic_module, 'EPIC_MAP_RIDER'):

            epic_map_rider = getattr(logic_module, 'EPIC_MAP_RIDER')
            select_all_rider = st.checkbox("Select/Deselect All Epics", value=True, key='select_all_epics_master_rider')
            # st.markdown("#### Configure Epics and Case Counts")
            # st.markdown("---")
            with st.expander("ℹ️ Configure Rider Epics and Case Counts", expanded=True):
                ppt_names = ["Single Pay", "Limited Pay (5 pay)", "Limited Pay (10 pay)", "Limited Pay (15 pay)", "Limited Pay (Pay till age 60)", "Regular Pay"]

                for epic_key, epic_desc in epic_map_rider.items():
                    toggle_key = None
                    ppt_names = ["Single Pay", "Limited Pay (5 pay)", "Limited Pay (10 pay)", "Limited Pay (15 pay)", "Limited Pay (Pay till age 60)", "Regular Pay"]
                    entry_age_ppt_ranges = {
                        "Single Pay": (18, 65),
                        "Limited Pay (5 pay)": (18, 65),
                        "Limited Pay (10 pay)": (18, 65),
                        "Limited Pay (15 pay)": (18, 65),
                        "Limited Pay (Pay till age 60)": (18, 55),
                        "Regular Pay": (18, 65)
                    }
                    policy_term_ppt_ranges = {
                        "Single Pay": (1, 5),
                        "Limited Pay (5 pay)": (10, 67),
                        "Limited Pay (10 pay)": (15, 67),
                        "Limited Pay (15 pay)": (20, 67),
                        "Limited Pay (Pay till age 60)": (5, 67),
                        "Regular Pay": (5, 67)
                    }
                    maturity_age_ppt_ranges = {
                        "Single Pay": (23, 75),
                        "Limited Pay (5 pay)": (23, 75),
                        "Limited Pay (10 pay)": (23, 75),
                        "Limited Pay (15 pay)": (23, 75),
                        "Limited Pay (Pay till age 60)": (23, 75),
                        "Regular Pay": (23, 75)
                    }
                    premium_paying_ppt_ranges = {
                        "Single Pay": (1, 1),
                        "Limited Pay (5 pay)": (5, 5),
                        "Limited Pay (10 pay)": (10, 10),
                        "Limited Pay (15 pay)": (15, 15),
                        "Limited Pay (Pay till age 60)": (5, 42),
                        "Regular Pay": (5, 67)
                    }
                    sum_assured_ranges = {
                        "Single Pay": (250000, 3000000),
                        "Others": (250000, 1000000),
                    }

                    if count_mode == "Set Individual Counts for Each Epic":
                        if epic_key == "EntryAge" or epic_key == "PremiumPayingTerm" or epic_key == "PolicyTerm" or epic_key == "MaturityAge":

                            is_selected = st.checkbox(epic_desc, value=select_all_rider, key=f"epic_cb_{epic_key}_rider")
                            with st.expander("Show/Hide PPT Configuration", expanded=False):
                                ppt_age_ranges, ppt_pos_counts, ppt_neg_counts, ppt_enabled = {}, {}, {}, {}

                                header = st.columns([0.5, 2, 2, 1, 1])
                                # with header[0]: st.markdown("**Enable**")
                                with header[1]: st.markdown("**PPT Name**")
                                with header[2]: st.markdown("**Min/Max**")
                                with header[3]: st.markdown("**Pos**")
                                with header[4]: st.markdown("**Neg**")

                                for ppt in ppt_names:
                                    row = st.columns([0.5, 2, 2, 1, 1])
                                    with row[0]:
                                        enabled = st.checkbox("Enable", value=is_selected, key=f"ppt_enabled_{epic_key}_{ppt}_rider", label_visibility="collapsed")
                                    with row[1]: st.markdown(ppt)
                                    with row[2]:
                                        if(epic_key == "EntryAge"):
                                            min_age, max_age = st.slider("Entry Age", 0, 85, entry_age_ppt_ranges[ppt], key=f"entry_age_slider_{epic_key}_{ppt}_rider",
                                                                    label_visibility="collapsed")
                                        elif(epic_key == "PolicyTerm"):
                                            min_age, max_age = st.slider("Policy Term", 5, 80, policy_term_ppt_ranges[ppt], key=f"entry_age_slider_{epic_key}_{ppt}_rider",
                                                                    label_visibility="collapsed")
                                        elif(epic_key == "MaturityAge"):
                                            min_age, max_age = st.slider("Maturity Age", 19, 75, maturity_age_ppt_ranges[ppt], key=f"maturity_age_slider_{epic_key}_{ppt}_rider",
                                                                    label_visibility="collapsed")
                                        else:
                                            if(premium_paying_ppt_ranges[ppt][0] == premium_paying_ppt_ranges[ppt][1]):
                                                min_age = max_age = st.slider("Entry Age", 0, 85, premium_paying_ppt_ranges[ppt][0], key=f"entry_age_slider_{epic_key}_{ppt}_rider", label_visibility="collapsed")
                                            else:
                                                min_age, max_age = st.slider("Entry Age", 0, 85, premium_paying_ppt_ranges[ppt], key=f"entry_age_slider_{epic_key}_{ppt}_rider", label_visibility="collapsed")
                                    with row[3]:
                                        pos = st.number_input("Pos", 0, value=5, key=f"epic_pos_{epic_key}_{ppt}_rider", label_visibility="collapsed")
                                    with row[4]:
                                        neg = st.number_input("Neg", 0, value=5, key=f"epic_neg_{epic_key}_{ppt}_rider", label_visibility="collapsed")

                                    if enabled:
                                        ppt_age_ranges[ppt] = (min_age, max_age)
                                        ppt_pos_counts[ppt] = pos
                                        ppt_neg_counts[ppt] = neg
                                        ppt_enabled[ppt] = True
                                    else:
                                        ppt_enabled[ppt] = False

                                if is_selected and any(ppt_enabled.values()):
                                    selected_epics_rider.append(epic_key)
                                    epic_counts_rider[epic_key] = {
                                        "ppt_age_ranges": ppt_age_ranges,
                                        "ppt_pos_counts": ppt_pos_counts,
                                        "ppt_neg_counts": ppt_neg_counts,
                                        "ppt_enabled": ppt_enabled
                                    }

                        elif epic_key == "PaymentFrequency":
                            row = st.columns([2, 1.5, 1.5])
                            with row[0]:
                                is_selected = st.checkbox(epic_desc, value=select_all_rider, key=f"epic_cb_{epic_key}_rider")
                            with row[1]:
                                pos_count = st.number_input(f"Pos {epic_key}", min_value=0, value=5, key=f"epic_pos_{epic_key}_rider", label_visibility="collapsed", placeholder="Pos")
                            with row[2]:
                                neg_count = st.number_input(f"Neg {epic_key}", min_value=0, value=5, key=f"epic_neg_{epic_key}_rider", label_visibility="collapsed", placeholder="Neg")

                            frequency_options = ["Annual", "Half-Yearly", "Quarterly", "Monthly", "Single Pay"]
                            frequency_map = {"Annual": 1, "Half-Yearly": 2, "Quarterly": 3, "Monthly": 4, "Single Pay": 5}
                            freq_cols = st.columns(len(frequency_options)+1)
                            selected_frequencies = []
                            for i, freq in enumerate(frequency_options):
                                with freq_cols[i+1]:
                                    if st.checkbox(freq, value=is_selected, key=f"freq_cb_{freq}_rider"):
                                        selected_frequencies.append(freq)

                            mapped_frequencies = [frequency_map[f] for f in selected_frequencies]

                            if is_selected:
                                selected_epics_rider.append(epic_key)
                                epic_counts_rider[epic_key] = {
                                    "positive": pos_count,
                                    "negative": neg_count,
                                    "payment_frequency_options": mapped_frequencies
                                }

                        else:
                            # For other epics, use slider for min/max and number inputs for pos/neg
                            row = st.columns([2, 1.5, 1.5])
                            with row[0]:
                                is_selected = st.checkbox(epic_desc, value=select_all_rider, key=f"epic_cb_{epic_key}_rider")
                            with row[1]:
                                pos_count = st.number_input(f"Pos {epic_key}", min_value=0, value=5, key=f"epic_pos_{epic_key}_rider", label_visibility="collapsed", placeholder="Pos")
                            with row[2]:
                                neg_count = st.number_input(f"Neg {epic_key}", min_value=0, value=5, key=f"epic_neg_{epic_key}_rider", label_visibility="collapsed", placeholder="Neg")
                            if is_selected:
                                selected_epics_rider.append(epic_key)
                                epic_counts_rider[epic_key] = {
                                    "positive": pos_count,
                                    "negative": neg_count
                                }

                    else:  # Apply Same Count to All Epics
                        if epic_key == "EntryAge" or epic_key == "PremiumPayingTerm" or epic_key == "PolicyTerm" or epic_key == "MaturityAge":

                            is_selected = st.checkbox(epic_desc, value=select_all_rider, key=f"epic_cb_{epic_key}_rider")
                            with st.expander("Show/Hide PPT Configuration", expanded=False):
                                ppt_age_ranges, ppt_enabled = {}, {}

                                for ppt in ppt_names:
                                    row = st.columns([0.5, 2, 2])
                                    with row[0]:
                                        enabled = st.checkbox("Enable", value=is_selected, key=f"ppt_enabled_all_{epic_key}_{ppt}_rider", label_visibility="collapsed")
                                    with row[1]: st.markdown(ppt)
                                    with row[2]:
                                        if(epic_key == "EntryAge"):
                                            min_age, max_age = st.slider("Entry Age", 0, 85, entry_age_ppt_ranges[ppt], key=f"entry_age_slider_{epic_key}_{ppt}_rider",
                                                                    label_visibility="collapsed")
                                        elif(epic_key == "PolicyTerm"):
                                            min_age, max_age = st.slider("Policy Term", 5, 80, policy_term_ppt_ranges[ppt], key=f"entry_age_slider_{epic_key}_{ppt}_rider",
                                                                    label_visibility="collapsed")
                                        elif(epic_key == "MaturityAge"):
                                            min_age, max_age = st.slider("Maturity Age", 19, 75, maturity_age_ppt_ranges[ppt], key=f"maturity_age_slider_{epic_key}_{ppt}_rider",
                                                                    label_visibility="collapsed")
                                        else:
                                            if(premium_paying_ppt_ranges[ppt][0] == premium_paying_ppt_ranges[ppt][1]):
                                                min_age = max_age = st.slider("Entry Age", 0, 85, premium_paying_ppt_ranges[ppt][0], key=f"entry_age_slider_{epic_key}_{ppt}_rider", label_visibility="collapsed")
                                            else:
                                                min_age, max_age = st.slider("Entry Age", 0, 85, premium_paying_ppt_ranges[ppt], key=f"entry_age_slider_{epic_key}_{ppt}_rider", label_visibility="collapsed")
                                    if enabled:
                                        ppt_age_ranges[ppt] = (min_age, max_age)
                                        ppt_enabled[ppt] = True
                                    else:
                                        ppt_enabled[ppt] = False

                                if is_selected and any(ppt_enabled.values()):
                                    selected_epics_rider.append(epic_key)
                                    epic_counts_rider[epic_key] = {
                                        "ppt_age_ranges": ppt_age_ranges,
                                        "ppt_enabled": ppt_enabled,
                                        "positive": num_positive_global,
                                        "negative": num_negative_global
                                    }

                        elif epic_key == "PaymentFrequency":
                            is_selected = st.checkbox(epic_desc, value=select_all_rider, key=f"epic_cb_{epic_key}_rider")
                            frequency_options = ["Annual", "Half-Yearly", "Quarterly", "Monthly", "Single Pay"]
                            frequency_map = {"Annual": 1, "Half-Yearly": 2, "Quarterly": 3, "Monthly": 4, "Single Pay": 5}
                            freq_cols = st.columns(len(frequency_options)+1)
                            selected_frequencies = []
                            for i, freq in enumerate(frequency_options):
                                with freq_cols[i+1]:
                                    if st.checkbox(freq, value=is_selected, key=f"freq_cb_{freq}_rider"):
                                        selected_frequencies.append(freq)

                            mapped_frequencies = [frequency_map[f] for f in selected_frequencies]

                            if is_selected:
                                selected_epics_rider.append(epic_key)
                                epic_counts_rider[epic_key] = {
                                    "positive": num_positive_global,
                                    "negative": num_negative_global,
                                    "payment_frequency_options": mapped_frequencies
                                }

                        else:
                            is_selected = st.checkbox(epic_desc, value=select_all_rider, key=f"epic_cb_{epic_key}_rider")
                            if is_selected:
                                selected_epics_rider.append(epic_key)
                                epic_counts_rider[epic_key] = {"positive": num_positive_global, "negative": num_negative_global}

                # print(epic_counts_rider)
            # print("Rider Epics Selected:", selected_epics_rider)

# --- Sidebar buttons for actions ---
with st.sidebar:
    # st.divider()
    st.header("Generate")
    if st.button("🚀 Generate Test Cases", type="primary", disabled=st.session_state.processing, use_container_width=True):
        if not st.session_state.selected_module_name_py:
            st.warning("Please select a product.")
        elif not (selected_epics or selected_epics_rider):
            st.warning("Please select at least one epic to generate from the main screen.")
        else:
            st.session_state.processing = True
            st.session_state.epic_counts_to_generate = epic_counts
            st.session_state.epic_counts_to_generate_rider = epic_counts_rider
            st.rerun()

    if st.session_state.generated_df is not None:
        if st.button("🧹 Clear Results & Start Over", use_container_width=True, disabled=st.session_state.processing):
            st.session_state.generated_df = None
            st.session_state.processing = False
            st.rerun()

# --- Main Canvas Logic ---
if st.session_state.processing and st.session_state.selected_module_name_py:
    with st.spinner(f"Generating test cases... Please wait."):
        logic_module = load_logic_module(
            st.session_state.selected_module_name_py,
            override_display_name=st.session_state.get('product_display_name_input'),
            override_product_code=st.session_state.get('product_code_input')
        )
        if logic_module:
            if hasattr(logic_module, 'generate_test_cases') and callable(logic_module.generate_test_cases):
                try:
                    df = logic_module.generate_test_cases(
                        epic_counts=st.session_state.epic_counts_to_generate,
                        selected_epics=list(st.session_state.epic_counts_to_generate.keys()),
                        epic_counts_rider=st.session_state.epic_counts_to_generate_rider,
                        selected_epics_rider=list(st.session_state.epic_counts_to_generate_rider.keys())
                        )
                    st.session_state.generated_df = df
                    st.success(f"Successfully generated {len(df)} test cases!")
                except Exception as e:
                    st.error(f"Error during test case generation:")
                    st.exception(e)
                    st.session_state.generated_df = None
            else:
                st.error(f"Module does not have a 'generate_test_cases' function.")
                st.session_state.generated_df = None
        else:
            st.error(f"Failed to load the logic module.")
            st.session_state.generated_df = None
    st.session_state.processing = False
    st.rerun()

elif st.session_state.generated_df is not None:
    df_to_display = st.session_state.generated_df

    st.header(f"Generated using: {st.session_state.selected_display_name}")
    st.divider()

    display_generation_summary(df_to_display)
    st.divider()

    st.subheader(f"📑 Sample Data (10 random rows from {len(df_to_display)} total)")
    rule_columns_to_style = [col for col in df_to_display.columns if col.startswith('Rule_')]

    sample_df = df_to_display.sample(min(10, len(df_to_display)))
    # sample_df = sample_df.sort_values(by="TUID", ascending=True)
    st.dataframe(
        sample_df.style.apply(highlight_rule_outcomes, subset=rule_columns_to_style),
        height=400, use_container_width=True
    )
    st.divider()

    st.subheader("💾 Download Results")
    current_timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_prefix = f"{st.session_state.selected_module_name_py}_test_cases_{current_timestamp}"

    output_excel = BytesIO()
    with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
        df_to_display.to_excel(writer, index=False, sheet_name='TestCases')
    excel_data = output_excel.getvalue()

    csv_data = df_to_display.to_csv(index=False).encode('utf-8')

    col_dl1, col_dl2 = st.columns(2)
    with col_dl1:
        st.download_button(
            label="📥 Download Excel File (.xlsx)", data=excel_data,
            file_name=f"{file_prefix}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True, key="download_excel"
        )
    with col_dl2:
        st.download_button(
            label="📄 Download CSV File (.csv)", data=csv_data,
            file_name=f"{file_prefix}.csv", mime="text/csv",
            use_container_width=True, key="download_csv"
        )
    st.caption("Files will download automatically after clicking.")

elif not st.session_state.selected_module_name_py:
    st.info("👋 Welcome! Please select a product from the sidebar to begin.")

else:
    st.info(f"ℹ️ Configure your test run, then click 'Generate Test Cases' in the sidebar.")
