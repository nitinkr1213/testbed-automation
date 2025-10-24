# app.py
import streamlit as st
import pandas as pd
from datetime import date, datetime 
from io import BytesIO
import os
import importlib.util

APP_DIR = os.path.dirname(os.path.abspath(__file__))
LOGIC_MODULE_DIR = os.path.join(APP_DIR, "logic_modules")

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

def load_logic_module(module_name_py):
    try:
        module_path = os.path.join(LOGIC_MODULE_DIR, f"{module_name_py}.py")
        spec = importlib.util.spec_from_file_location(module_name_py, module_path)
        logic_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(logic_module)
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


# --- Sidebar Configuration ---
with st.sidebar:
    st.header("🛠️ Configuration")
    
    available_modules = get_available_logic_modules()
    if not available_modules:
        st.error(f"Logic module directory ('{LOGIC_MODULE_DIR}') not found or empty.")
        st.stop() 

    display_names = list(available_modules.keys())
    
    default_index = 0
    if st.session_state.get('selected_display_name') in display_names:
        default_index = display_names.index(st.session_state.selected_display_name)
    
    selected_display_name_from_ui = st.selectbox(
        "Select Product",
        options=display_names,
        index=default_index,
    )
    
    if selected_display_name_from_ui != st.session_state.selected_display_name:
        st.session_state.selected_display_name = selected_display_name_from_ui
        st.session_state.selected_module_name_py = available_modules[selected_display_name_from_ui]
        st.session_state.generated_df = None 
        st.session_state.processing = False 
        st.rerun()

    st.divider()
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
        logic_module = load_logic_module(st.session_state.selected_module_name_py)
        if logic_module and hasattr(logic_module, 'EPIC_MAP'):

            epic_map = getattr(logic_module, 'EPIC_MAP')
            select_all = st.checkbox("Select/Deselect All Epics", value=True, key='select_all_epics_master')
            st.markdown("#### Configure Epics and Case Counts")
            # st.markdown("---")
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
                                min_sp = st.number_input("Min SinglePay", min_value=0, value=2500000, key=f"min_sp_{epic_key}", label_visibility="collapsed")
                            with row_sp[3]:
                                max_sp = st.number_input("Max SinglePay", min_value=min_sp, value=5000000, key=f"max_sp_{epic_key}", label_visibility="collapsed")
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
                                min_oth = st.number_input("Min Others", min_value=0, value=5000000, key=f"min_oth_{epic_key}", label_visibility="collapsed")
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
                                min_sp = st.number_input("Min SinglePay", min_value=0, value=2500000, key=f"min_sp_{epic_key}", label_visibility="collapsed")
                            with row_sp[3]:
                                max_sp = st.number_input("Max SinglePay", min_value=min_sp, value=5000000, key=f"max_sp_{epic_key}", label_visibility="collapsed")

                            row_oth = st.columns([0.5, 2, 1, 1])
                            with row_oth[0]:
                                oth = st.checkbox("Enable", value=is_selected, key=f"oth_enabled_{epic_key}", label_visibility="collapsed")
                            with row_oth[1]:
                                st.markdown("Others")
                            with row_oth[2]:
                                min_oth = st.number_input("Min Others", min_value=0, value=5000000, key=f"min_oth_{epic_key}", label_visibility="collapsed")

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
        logic_module = load_logic_module(st.session_state.selected_module_name_py)
        if logic_module and hasattr(logic_module, 'EPIC_MAP_RIDER'):

            epic_map_rider = getattr(logic_module, 'EPIC_MAP_RIDER')
            select_all_rider = st.checkbox("Select/Deselect All Epics", value=True, key='select_all_epics_master_rider')
            st.markdown("#### Configure Epics and Case Counts")
            # st.markdown("---")
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
                    "Single Pay": (19, 75),
                    "Limited Pay (5 pay)": (19, 75),
                    "Limited Pay (10 pay)": (19, 75),
                    "Limited Pay (15 pay)": (19, 75),
                    "Limited Pay (Pay till age 60)": (19, 75),
                    "Regular Pay": (19, 75)
                }
                premium_paying_ppt_ranges = {
                    "Single Pay": (1, 1),
                    "Limited Pay (5 pay)": (5, 5),
                    "Limited Pay (10 pay)": (10, 10),
                    "Limited Pay (15 pay)": (15, 15),
                    "Limited Pay (Pay till age 60)": (5, 42),
                    "Regular Pay": (5, 67)
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
                            selected_epics.append(epic_key)
                            epic_counts[epic_key] = {
                                "positive": pos_count,
                                "negative": neg_count,
                                "payment_frequency_options": mapped_frequencies
                            }
                    # elif epic_key == "SumAssuredValidation":
                    #     is_selected = st.checkbox(epic_desc, value=select_all_rider, key=f"epic_cb_{epic_key}_rider")
                    #     with st.expander("Show/Hide PPT Configuration", expanded=False):

                    #         header = st.columns([0.5, 2, 1, 1, 1, 1])
                    #         # with header[0]: st.markdown("**Enable**")
                    #         with header[1]: st.markdown("**PPT Type**")
                    #         with header[2]: st.markdown("**Min**")
                    #         with header[3]: st.markdown("**Max**")
                    #         with header[4]: st.markdown("**Pos**")
                    #         with header[5]: st.markdown("**Neg**")

                    #         row_sp = st.columns([0.5, 2, 1, 1, 1, 1])
                    #         with row_sp[0]:
                    #             sp = st.checkbox("Enable", value=is_selected, key=f"sa_enabled_{epic_key}_rider", label_visibility="collapsed")
                    #         with row_sp[1]:
                    #             st.markdown("SinglePay")
                    #         with row_sp[2]:
                    #             min_sp = st.number_input("Min SinglePay", min_value=0, value=2500000, key=f"min_sp_{epic_key}_rider", label_visibility="collapsed")
                    #         with row_sp[3]:
                    #             max_sp = st.number_input("Max SinglePay", min_value=min_sp, value=5000000, key=f"max_sp_{epic_key}_rider", label_visibility="collapsed")
                    #         with row_sp[4]:
                    #             pos_sp = st.number_input("Pos SinglePay", min_value=0, value=5, key=f"pos_sp_{epic_key}_rider", label_visibility="collapsed")
                    #         with row_sp[5]:
                    #             neg_sp = st.number_input("Neg SinglePay", min_value=0, value=5, key=f"neg_sp_{epic_key}_rider", label_visibility="collapsed")

                    #         row_oth = st.columns([0.5, 2, 1, 1, 1, 1])
                    #         with row_oth[0]:
                    #             oth = st.checkbox("Enable", value=is_selected, key=f"oth_enabled_{epic_key}_rider", label_visibility="collapsed")
                    #         with row_oth[1]:
                    #             st.markdown("Others")
                    #         with row_oth[2]:
                    #             min_oth = st.number_input("Min Others", min_value=0, value=5000000, key=f"min_oth_{epic_key}_rider", label_visibility="collapsed")
                    #         with row_oth[4]:
                    #             pos_oth = st.number_input("Pos Others", min_value=0, value=5, key=f"pos_oth_{epic_key}_rider", label_visibility="collapsed")
                    #         with row_oth[5]:
                    #             neg_oth = st.number_input("Neg Others", min_value=0, value=5, key=f"neg_oth_{epic_key}_rider", label_visibility="collapsed")

                    #         if is_selected:
                    #             selected_epics_rider.append(epic_key)
                    #             if epic_key not in epic_counts_rider:
                    #                 epic_counts_rider[epic_key] = {}
                    #             if sp:
                    #                 epic_counts_rider[epic_key]["Single Pay"] = {
                    #                     "min_val": min_sp,
                    #                     "max_val": max_sp,
                    #                     "positive": num_positive_global,
                    #                     "negative": num_negative_global
                    #                 }
                    #             if oth:
                    #                 epic_counts_rider[epic_key]["Others"] = {
                    #                     "min_val": min_oth,
                    #                     "positive": num_positive_global,
                    #                     "negative": num_negative_global
                    #                 }

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
                            selected_epics.append(epic_key)
                            epic_counts[epic_key] = {
                                "positive": num_positive_global,
                                "negative": num_negative_global,
                                "payment_frequency_options": mapped_frequencies
                            }
                    # elif epic_key == "SumAssuredValidation":
                    #     is_selected = st.checkbox(epic_desc, value=select_all_rider, key=f"epic_cb_{epic_key}_rider")
                    #     with st.expander("Show/Hide PPT Configuration", expanded=False):

                    #         header = st.columns([0.5, 2, 1, 1])
                    #         # with header[0]: st.markdown("**Enable**")
                    #         with header[1]: st.markdown("**PPT Type**")
                    #         with header[2]: st.markdown("**Min**")
                    #         with header[3]: st.markdown("**Max**")

                    #         row_sp = st.columns([0.5, 2, 1, 1])
                    #         with row_sp[0]:
                    #             sp = st.checkbox("Enable", value=is_selected, key=f"sa_enabled_{epic_key}_rider", label_visibility="collapsed")
                    #         with row_sp[1]:
                    #             st.markdown("SinglePay")
                    #         with row_sp[2]:
                    #             min_sp = st.number_input("Min SinglePay", min_value=0, value=2500000, key=f"min_sp_{epic_key}_rider", label_visibility="collapsed")
                    #         with row_sp[3]:
                    #             max_sp = st.number_input("Max SinglePay", min_value=min_sp, value=5000000, key=f"max_sp_{epic_key}_rider", label_visibility="collapsed")

                    #         row_oth = st.columns([0.5, 2, 1, 1])
                    #         with row_oth[0]:
                    #             oth = st.checkbox("Enable", value=is_selected, key=f"oth_enabled_{epic_key}_rider", label_visibility="collapsed")
                    #         with row_oth[1]:
                    #             st.markdown("Others")
                    #         with row_oth[2]:
                    #             min_oth = st.number_input("Min Others", min_value=0, value=5000000, key=f"min_oth_{epic_key}_rider", label_visibility="collapsed")

                    #         if is_selected:
                    #             selected_epics_rider.append(epic_key)
                    #             if epic_key not in epic_counts_rider:
                    #                 epic_counts_rider[epic_key] = {}
                    #             if sp:
                    #                 epic_counts_rider[epic_key]["Single Pay"] = {
                    #                     "min_val": min_sp,
                    #                     "max_val": max_sp,
                    #                     "positive": num_positive_global,
                    #                     "negative": num_negative_global
                    #                 }
                    #             if oth:
                    #                 epic_counts_rider[epic_key]["Others"] = {
                    #                     "min_val": min_oth,
                    #                     "positive": num_positive_global,
                    #                     "negative": num_negative_global
                    #                 }

                    else:
                        is_selected = st.checkbox(epic_desc, value=select_all_rider, key=f"epic_cb_{epic_key}_rider")
                        if is_selected:
                            selected_epics_rider.append(epic_key)
                            epic_counts_rider[epic_key] = {"positive": num_positive_global, "negative": num_negative_global}

                # print(epic_counts_rider)
            # print("Rider Epics Selected:", selected_epics_rider)

# --- Sidebar buttons for actions ---
with st.sidebar:
    st.divider()
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
        logic_module = load_logic_module(st.session_state.selected_module_name_py)
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


# To Do List:
# - [x] Add support for rider epics "keys" // done
