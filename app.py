import io
import json
import os
import re
from urllib.parse import urljoin

import pandas as pd
import pdfplumber
import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="DataMate AI", page_icon="🤖", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
PATTERNS = {
    # General / contact
    "Name": [r"(?:full\s*name|customer\s*name|applicant\s*name|name)\s*[:\-]\s*([A-Za-z][A-Za-z .'-]{2,80})"],
    "Email": [r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"],
    "Phone": [
        r"(?:\+?880[\s-]?)?01[3-9][\s-]?\d{3}[\s-]?\d{4}\b",
        r"\b(?:\+?\d[\d\s().-]{7,}\d)\b",
    ],
    "Address": [r"(?:address|location|located\s+at)\s*[:\-]\s*([^\n]{5,180})"],
    "Website": [r"https?://[^\s<>\"]+"],
    "Company": [r"(?:company|organization|organisation|employer)\s*[:\-]\s*([^\n]{2,120})"],
    "Job Title": [r"(?:job\s*title|designation|position|role|title)\s*[:\-]\s*([^\n]{2,100})"],

    # Bank / loan / customer data
    "Customer ID": [r"(?:customer\s*(?:id|no|number)|client\s*(?:id|no|number))\s*[:\-]\s*([^\n,;]{1,80})"],
    "Loan ID": [r"(?:loan\s*(?:id|no|number))\s*[:\-]\s*([^\n,;]{1,80})"],
    "Age": [r"(?:age)\s*[:\-]\s*(\d{1,3})"],
    "Gender": [r"(?:gender|sex)\s*[:\-]\s*([^\n,;]{1,30})"],
    "Marital Status": [r"(?:marital\s*status|married)\s*[:\-]\s*([^\n,;]{1,40})"],
    "Dependents": [r"(?:dependents?|number\s*of\s*dependents)\s*[:\-]\s*([^\n,;]{1,30})"],
    "Education": [r"(?:education|education\s*level)\s*[:\-]\s*([^\n,;]{1,80})"],
    "Employment Status": [r"(?:employment\s*status|employment|occupation)\s*[:\-]\s*([^\n,;]{1,100})"],
    "Self Employed": [r"(?:self[ _-]*employed)\s*[:\-]\s*([^\n,;]{1,30})"],
    "Applicant Income": [r"(?:applicant[ _-]*income|monthly\s*income|income)\s*[:\-]?\s*(?:৳|Tk|BDT|\$|USD)?\s*([\d,.]+)"],
    "Coapplicant Income": [r"(?:co[ _-]*applicant[ _-]*income|coapplicant[ _-]*income)\s*[:\-]?\s*(?:৳|Tk|BDT|\$|USD)?\s*([\d,.]+)"],
    "Annual Income": [r"(?:annual[ _-]*income|yearly[ _-]*income)\s*[:\-]?\s*(?:৳|Tk|BDT|\$|USD)?\s*([\d,.]+)"],
    "Loan Amount": [r"(?:loan[ _-]*amount|requested[ _-]*amount|principal)\s*[:\-]?\s*(?:৳|Tk|BDT|\$|USD)?\s*([\d,.]+)"],
    "Loan Term": [r"(?:loan[ _-]*(?:term|tenure)|term)\s*[:\-]\s*([^\n,;]{1,50})"],
    "Loan Purpose": [r"(?:loan[ _-]*purpose|purpose)\s*[:\-]\s*([^\n,;]{1,100})"],
    "Interest Rate": [r"(?:interest[ _-]*rate|rate\s*of\s*interest)\s*[:\-]?\s*([\d.]+%?)"],
    "Credit Score": [r"(?:credit[ _-]*score|cibil[ _-]*score)\s*[:\-]\s*(\d{2,4})"],
    "Credit History": [r"(?:credit[ _-]*history)\s*[:\-]\s*([^\n,;]{1,50})"],
    "Property Area": [r"(?:property[ _-]*area|area)\s*[:\-]\s*([^\n,;]{1,80})"],
    "Property Value": [r"(?:property[ _-]*value|property[ _-]*price)\s*[:\-]?\s*(?:৳|Tk|BDT|\$|USD)?\s*([\d,.]+)"],
    "Debt-to-Income Ratio": [r"(?:debt[ _-]*to[ _-]*income|dti)(?:\s*ratio)?\s*[:\-]?\s*([\d.]+%?)"],
    "Existing EMI": [r"(?:existing[ _-]*emi|emi)\s*[:\-]?\s*(?:৳|Tk|BDT|\$|USD)?\s*([\d,.]+)"],
    "Loan Status": [r"(?:loan[ _-]*status|approval[ _-]*status|status)\s*[:\-]\s*([^\n,;]{1,50})"],

    # Financial / transaction data
    "Account Number": [r"(?:account\s*(?:number|no)|a/c\s*(?:number|no))\s*[:\-]\s*([^\n,;]{3,60})"],
    "Transaction ID": [r"(?:transaction\s*(?:id|no|number)|txn\s*(?:id|no))\s*[:\-]\s*([^\n,;]{2,80})"],
    "Transaction Date": [r"(?:transaction\s*date|date)\s*[:\-]\s*([^\n,;]{4,50})"],
    "Balance": [r"(?:balance|account\s*balance)\s*[:\-]?\s*(?:৳|Tk|BDT|\$|USD)?\s*([\d,.]+)"],

    # Product / e-commerce
    "Price": [r"(?:price|cost|amount)\s*[:\-]?\s*(?:৳|Tk|BDT|\$|USD|€|£)?\s*[\d,]+(?:\.\d{1,2})?"],
    "Product": [r"(?:product|product\s*name|item)\s*[:\-]\s*([^\n]{2,120})"],
    "SKU": [r"(?:sku|product\s*code|item\s*code)\s*[:\-]\s*([^\n]{2,80})"],
    "Category": [r"(?:category|type)\s*[:\-]\s*([^\n]{2,100})"],
    "Description": [r"(?:description|details)\s*[:\-]\s*([^\n]{5,300})"],
}

ALIASES = {
    "name": "Name", "full name": "Name", "email": "Email", "email address": "Email",
    "phone": "Phone", "phone number": "Phone", "mobile": "Phone", "address": "Address",
    "location": "Address", "website": "Website", "url": "Website", "company": "Company",
    "organization": "Company", "organisation": "Company", "job title": "Job Title",
    "designation": "Job Title", "position": "Job Title",
    "customer id": "Customer ID", "customer number": "Customer ID", "loan id": "Loan ID",
    "age": "Age", "gender": "Gender", "marital status": "Marital Status", "dependents": "Dependents",
    "education": "Education", "employment status": "Employment Status", "self employed": "Self Employed",
    "applicant income": "Applicant Income", "coapplicant income": "Coapplicant Income",
    "annual income": "Annual Income", "loan amount": "Loan Amount", "loan term": "Loan Term",
    "loan tenure": "Loan Term", "loan purpose": "Loan Purpose", "interest rate": "Interest Rate",
    "credit score": "Credit Score", "credit history": "Credit History", "property area": "Property Area",
    "property value": "Property Value", "debt to income ratio": "Debt-to-Income Ratio",
    "dti": "Debt-to-Income Ratio", "existing emi": "Existing EMI", "loan status": "Loan Status",
    "approval status": "Loan Status", "account number": "Account Number", "transaction id": "Transaction ID",
    "transaction date": "Transaction Date", "balance": "Balance",
    "price": "Price", "cost": "Price", "product": "Product", "product name": "Product",
    "sku": "SKU", "category": "Category", "description": "Description",
}

WORK_AREAS = {
    "Data Mining": "Find useful information and patterns from the supplied source.",
    "Data Formatting": "Clean, standardize, deduplicate and reshape tabular data.",
    "Data Cleaning": "Interactively edit rows/columns, handle missing values, remove duplicates and fix data quality problems.",
    "Data Scraping": "Collect structured information from a public webpage.",
    "Data Extraction": "Extract selected fields such as names, emails, phones and prices.",
    "Data Collection": "Combine collected information into a clean table.",
    "Data Analysis": "Generate a quick summary for numeric and categorical columns.",
    "Product Listing": "Prepare product-ready rows with product, price, SKU, category and description.",
    "E-commerce Data Entry": "Prepare store-ready product data for import or manual entry.",
}


# -----------------------------
# Developer profile + EmailJS
# -----------------------------
def _setting(section, key, env_name, default=""):
    """Read a setting from Streamlit secrets first, then from an environment variable."""
    value = ""
    try:
        section_data = st.secrets.get(section, {})
        if section_data:
            value = section_data.get(key, "")
    except Exception:
        value = ""
    value = value or os.getenv(env_name, "") or default
    return str(value).strip()


def developer_settings():
    return {
        "name": _setting("developer", "name", "DATAMATE_DEVELOPER_NAME", "Md. Ryhan Munna"),
        "role": _setting("developer", "role", "DATAMATE_DEVELOPER_ROLE", "Data Analyst • CSE Student"),
        "github": _setting("developer", "github", "DATAMATE_GITHUB_URL", "https://github.com/MDRyhanMunna"),
        "portfolio": _setting(
            "developer",
            "portfolio",
            "DATAMATE_PORTFOLIO_URL",
            "https://rayhanswork.lovable.app",
        ),
    }


def emailjs_settings():
    return {
        "service_id": _setting("emailjs", "service_id", "EMAILJS_SERVICE_ID", "service_152vrq4"),
        "template_id": _setting("emailjs", "template_id", "EMAILJS_TEMPLATE_ID", "template_8qbjzwf"),
        "public_key": _setting("emailjs", "public_key", "EMAILJS_PUBLIC_KEY", "IOt03A_3IO8PHZJVr"),
        # Optional. Do not commit this value to GitHub.
        "private_key": _setting("emailjs", "private_key", "EMAILJS_PRIVATE_KEY"),
    }


def emailjs_is_configured():
    cfg = emailjs_settings()
    return all(cfg.get(k) for k in ("service_id", "template_id", "public_key"))


def send_emailjs_message(sender_name, sender_email, message):
    """Send the developer contact form through EmailJS's REST API."""
    cfg = emailjs_settings()
    missing = [k for k in ("service_id", "template_id", "public_key") if not cfg.get(k)]
    if missing:
        raise RuntimeError(
            "EmailJS is not configured yet. Add service_id, template_id and public_key "
            "to .streamlit/secrets.toml or environment variables."
        )

    dev = developer_settings()
    payload = {
        "service_id": cfg["service_id"],
        "template_id": cfg["template_id"],
        "user_id": cfg["public_key"],
        "template_params": {
            "from_name": sender_name,
            "from_email": sender_email,
            "reply_to": sender_email,
            "message": message,
            "to_name": dev["name"],
            "project_name": "DataMate AI",
        },
    }
    if cfg.get("private_key"):
        payload["accessToken"] = cfg["private_key"]

    response = requests.post(
        "https://api.emailjs.com/api/v1.0/email/send",
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=25,
    )
    if not response.ok:
        detail = (response.text or response.reason or "Unknown EmailJS error").strip()
        raise RuntimeError(f"EmailJS error {response.status_code}: {detail[:300]}")
    return True


def developer_panel_content():
    dev = developer_settings()

    st.markdown(
        """
        <div class="developer-hero">
            <div class="developer-avatar">👨‍💻</div>
            <div>
                <div class="developer-name">{name}</div>
                <div class="developer-role"><span class="online-dot"></span>{role} · DataMate AI</div>
            </div>
        </div>
        """.format(name=dev["name"], role=dev["role"]),
        unsafe_allow_html=True,
    )

    st.markdown("#### ABOUT")
    st.markdown(
        """
        <div class="developer-card">
        DataMate AI is a data-work assistant for collecting, extracting, formatting, analyzing and exporting information from files and public webpages. It supports PDF, CSV, Excel, JSON, TXT, URLs and pasted text, with downloadable CSV, Excel and JSON results.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("#### BUILT WITH")
    st.markdown(
        """
        <div class="tech-tags">
          <span>🐍 Python</span><span>⚡ Streamlit</span><span>🐼 Pandas</span>
          <span>🌐 BeautifulSoup</span><span>📄 pdfplumber</span><span>✉️ EmailJS</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if dev.get("github") or dev.get("portfolio"):
        st.markdown("#### FIND ME ONLINE")
        c1, c2 = st.columns(2)
        if dev.get("github"):
            c1.link_button("🐙 GitHub ↗", dev["github"], use_container_width=True)
        if dev.get("portfolio"):
            c2.link_button("🌎 Portfolio ↗", dev["portfolio"], use_container_width=True)

    st.markdown("#### CONTACT ME")
    configured = emailjs_is_configured()
    if not configured:
        st.info(
            "EmailJS setup is waiting for your IDs. Add them to `.streamlit/secrets.toml` "
            "using the included example file. The form will start sending messages after that."
        )

    with st.form("developer_contact_form", clear_on_submit=True):
        sender_name = st.text_input("Your name", placeholder="Your name")
        sender_email = st.text_input("Your email", placeholder="you@example.com")
        message = st.text_area("Message", placeholder="Write your message...", height=150)
        submitted = st.form_submit_button("Send Message", type="primary", use_container_width=True)

    if submitted:
        sender_name = sender_name.strip()
        sender_email = sender_email.strip()
        message = message.strip()
        if not sender_name:
            st.error("Please enter your name.")
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", sender_email):
            st.error("Please enter a valid email address.")
        elif len(message) < 5:
            st.error("Please write a message of at least 5 characters.")
        elif len(message) > 5000:
            st.error("Please keep the message under 5,000 characters.")
        else:
            try:
                send_emailjs_message(sender_name, sender_email, message)
                st.success("Message sent successfully. Thank you!")
            except Exception as exc:
                st.error(str(exc))


if hasattr(st, "dialog"):
    @st.dialog("Developer", width="large")
    def developer_dialog():
        developer_panel_content()
else:
    def developer_dialog():
        st.warning("Update Streamlit to use the developer popup.")
        developer_panel_content()



def clean_text(value):
    return re.sub(r"\s+", " ", str(value)).strip(" \t\r\n,;|")


def unique(values):
    out = []
    seen = set()
    for value in values:
        value = clean_text(value)
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            out.append(value)
    return out


def extract_field(text, field):
    patterns = PATTERNS.get(field, [rf"(?:{re.escape(field)})\s*[:\-]\s*([^\n]{{2,180}})"])
    values = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            values.append(match.group(1) if match.lastindex else match.group(0))
    return unique(values)


def request_fields(request):
    found = []
    lowered = request.lower()
    for alias, field in sorted(ALIASES.items(), key=lambda x: len(x[0]), reverse=True):
        if re.search(rf"\b{re.escape(alias)}\b", lowered) and field not in found:
            found.append(field)
    return found


def normalize_field_name(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def source_columns_from_request(request, df):
    """Detect actual CSV/Excel/JSON columns mentioned in a natural-language instruction."""
    if df is None or not request.strip():
        return []
    lowered = normalize_field_name(request)
    found = []
    for col in df.columns:
        norm = normalize_field_name(col)
        if norm and re.search(rf"\b{re.escape(norm)}\b", lowered):
            found.append(str(col))
    return found


def resolve_fields(request, selected_fields, df=None):
    """Use source columns + known aliases from the instruction; fall back to UI selections."""
    if request.strip():
        found = source_columns_from_request(request, df)
        for field in request_fields(request):
            if field not in found:
                found.append(field)
        if found:
            return found
    return list(selected_fields)


def select_dataframe_fields(df, fields):
    """Select real table columns using exact or normalized names."""
    if df is None:
        return None
    lookup = {normalize_field_name(col): col for col in df.columns}
    selected = []
    for field in fields:
        if field in df.columns and field not in selected:
            selected.append(field)
            continue
        norm = normalize_field_name(field)
        if norm in lookup and lookup[norm] not in selected:
            selected.append(lookup[norm])
            continue
        # Match common standard field labels to similarly named source columns.
        for col_norm, col in lookup.items():
            if norm and (norm == col_norm or norm in col_norm or col_norm in norm):
                if col not in selected:
                    selected.append(col)
                break
    return df[selected].copy() if selected else pd.DataFrame()


def extract_records(text, fields):
    data = {field: extract_field(text, field) for field in fields}
    n = max([len(values) for values in data.values()] + [1])
    rows = []
    for i in range(n):
        rows.append({field: data[field][i] if i < len(data[field]) else "" for field in fields})
    return pd.DataFrame(rows)


def read_pdf(file_obj):
    with pdfplumber.open(file_obj) as pdf:
        parts = []
        for i, page in enumerate(pdf.pages, 1):
            parts.append(f"PAGE {i}\n{page.extract_text() or ''}")
        return "\n\n".join(parts)


def read_web(url):
    response = requests.get(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
        },
        timeout=25,
        allow_redirects=True,
    )
    if response.status_code in (401, 403, 429):
        raise PermissionError(str(response.status_code))
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    links = []
    for anchor in soup.find_all("a", href=True):
        label = " ".join(anchor.get_text(" ", strip=True).split())
        href = urljoin(response.url, anchor["href"])
        if label or href:
            links.append({"Text": label, "URL": href})
    return text, links


def dataframe_to_text(df):
    if df is None or df.empty:
        return ""
    return df.fillna("").astype(str).to_csv(index=False)


def clean_dataframe(df):
    out = df.copy()
    out.columns = [clean_text(c).replace(" ", "_") for c in out.columns]
    for col in out.columns:
        if out[col].dtype == "object":
            out[col] = out[col].astype(str).map(clean_text)
            out[col] = out[col].replace({"nan": "", "None": ""})
    out = out.drop_duplicates().reset_index(drop=True)
    return out


def quick_analysis(df):
    rows = []
    for col in df.columns:
        series = df[col]
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum() > 0 and numeric.notna().sum() >= max(2, len(series) // 2):
            rows.append({
                "Column": col,
                "Type": "Numeric",
                "Non-empty": int(series.notna().sum()),
                "Unique": int(series.nunique(dropna=True)),
                "Mean": round(float(numeric.mean()), 4) if numeric.notna().any() else "",
                "Min": float(numeric.min()) if numeric.notna().any() else "",
                "Max": float(numeric.max()) if numeric.notna().any() else "",
            })
        else:
            mode = series.mode(dropna=True)
            rows.append({
                "Column": col,
                "Type": "Text/Categorical",
                "Non-empty": int(series.notna().sum()),
                "Unique": int(series.nunique(dropna=True)),
                "Mean": "",
                "Min": "",
                "Max": mode.iloc[0] if not mode.empty else "",
            })
    return pd.DataFrame(rows)


def ollama_extract(text, request, model, endpoint):
    prompt = (
        "You are a precise data extraction assistant.\n"
        f"Task: {request}\n"
        "Return JSON only in this format: {\"records\":[{\"field\":\"value\"}]}\n"
        "Do not invent facts. Use an empty string when a value is missing.\n"
        "SOURCE:\n" + text[:60000]
    )
    response = requests.post(
        endpoint.rstrip("/") + "/api/generate",
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=120,
    )
    response.raise_for_status()
    raw = response.json().get("response", "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    return pd.DataFrame(json.loads(raw).get("records", []))


def make_downloads(df, prefix="datamate_result"):
    csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
    excel = io.BytesIO()
    with pd.ExcelWriter(excel, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="DataMate Result")
    json_bytes = df.to_json(orient="records", force_ascii=False, indent=2).encode("utf-8")
    return csv_bytes, excel.getvalue(), json_bytes


# -----------------------------
# Interactive data-cleaning workspace
# -----------------------------
MISSING_TEXT_TOKENS = {"", "na", "n/a", "n.a.", "null", "none", "nan", "?", "-", "--", "missing"}


def missing_mask(series):
    """Treat real NaN plus common blank/missing text markers as missing."""
    mask = series.isna()
    if pd.api.types.is_object_dtype(series.dtype) or pd.api.types.is_string_dtype(series.dtype):
        normalized = series.astype("string").str.strip().str.lower()
        mask = mask | normalized.isin(MISSING_TEXT_TOKENS)
    return mask.fillna(True)


def missing_report(df):
    rows = []
    total = max(len(df), 1)
    for col in df.columns:
        count = int(missing_mask(df[col]).sum())
        rows.append({
            "Column": str(col),
            "Missing": count,
            "Missing %": round(count * 100 / total, 2),
            "Data type": str(df[col].dtype),
            "Unique": int(df[col].nunique(dropna=True)),
        })
    if not rows:
        return pd.DataFrame(columns=["Column", "Missing", "Missing %", "Data type", "Unique"])
    return pd.DataFrame(rows).sort_values(["Missing", "Column"], ascending=[False, True]).reset_index(drop=True)


def normalize_missing_in_columns(df, columns):
    out = df.copy()
    for col in columns:
        if col not in out.columns:
            continue
        mask = missing_mask(out[col])
        if mask.any():
            out.loc[mask, col] = pd.NA
    return out


def is_numeric_like(series):
    non_missing = series[~missing_mask(series)]
    if non_missing.empty:
        return False
    converted = pd.to_numeric(non_missing, errors="coerce")
    return converted.notna().mean() >= 0.8


def fill_missing_values(df, columns, strategy, custom_value=""):
    out = normalize_missing_in_columns(df, columns)
    for col in columns:
        if col not in out.columns:
            continue
        mask = out[col].isna()
        if not mask.any():
            continue
        if strategy == "Automatic (numeric median, text mode)":
            strategy_for_col = "Median" if is_numeric_like(out[col]) else "Mode"
        else:
            strategy_for_col = strategy

        if strategy_for_col in ("Mean", "Median"):
            numeric = pd.to_numeric(out[col], errors="coerce")
            value = numeric.mean() if strategy_for_col == "Mean" else numeric.median()
            if pd.notna(value):
                out.loc[mask, col] = value
        elif strategy_for_col == "Mode":
            available = out.loc[~mask, col]
            mode = available.mode(dropna=True)
            if not mode.empty:
                out.loc[mask, col] = mode.iloc[0]
        elif strategy_for_col == "Custom value":
            out.loc[mask, col] = custom_value
    return out


def parse_row_numbers(text, max_rows):
    """Parse values such as 1,3,5-8 as 1-based row numbers."""
    rows = set()
    for part in str(text).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            left, right = part.split("-", 1)
            try:
                a, b = int(left), int(right)
                if a > b:
                    a, b = b, a
                rows.update(range(a, b + 1))
            except ValueError:
                continue
        else:
            try:
                rows.add(int(part))
            except ValueError:
                continue
    return sorted(r for r in rows if 1 <= r <= max_rows)


def convert_boolean(series):
    mapping = {
        "true": True, "yes": True, "y": True, "1": True, "t": True,
        "false": False, "no": False, "n": False, "0": False, "f": False,
    }
    def cv(v):
        if pd.isna(v):
            return pd.NA
        key = str(v).strip().lower()
        return mapping.get(key, pd.NA)
    return series.map(cv).astype("boolean")


def push_cleaning_history():
    current = st.session_state.get("cleaning_df")
    if isinstance(current, pd.DataFrame):
        history = st.session_state.get("cleaning_history", [])
        history.append(current.copy(deep=True))
        st.session_state.cleaning_history = history[-15:]


def set_cleaning_df(new_df, add_history=True):
    if add_history:
        push_cleaning_history()
    st.session_state.cleaning_df = new_df.reset_index(drop=True).copy()
    st.session_state.cleaning_revision = int(st.session_state.get("cleaning_revision", 0)) + 1


def initialize_cleaning_workspace(df, source_id, force=False):
    if df is None:
        return
    if force or st.session_state.get("cleaning_source_id") != source_id:
        st.session_state.cleaning_original_df = df.copy(deep=True).reset_index(drop=True)
        st.session_state.cleaning_df = df.copy(deep=True).reset_index(drop=True)
        st.session_state.cleaning_source_id = source_id
        st.session_state.cleaning_history = []
        st.session_state.cleaning_revision = int(st.session_state.get("cleaning_revision", 0)) + 1


def render_cleaning_workspace():
    df = st.session_state.get("cleaning_df")
    if not isinstance(df, pd.DataFrame):
        st.warning("Upload a CSV, Excel or JSON table first, or extract a result and send it to Data Cleaning.")
        return

    st.subheader("2. Data Cleaning Workspace")
    miss_total = int(sum(int(missing_mask(df[c]).sum()) for c in df.columns)) if len(df.columns) else 0
    duplicates = int(df.duplicated().sum()) if len(df) else 0
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Rows", len(df))
    m2.metric("Columns", len(df.columns))
    m3.metric("Missing cells", miss_total)
    m4.metric("Duplicate rows", duplicates)

    top1, top2, top3 = st.columns([1, 1, 2])
    if top1.button("↶ Undo", use_container_width=True, disabled=not st.session_state.get("cleaning_history")):
        history = st.session_state.get("cleaning_history", [])
        if history:
            st.session_state.cleaning_df = history.pop()
            st.session_state.cleaning_history = history
            st.session_state.cleaning_revision = int(st.session_state.get("cleaning_revision", 0)) + 1
            st.rerun()
    if top2.button("⟲ Reset original", use_container_width=True):
        original = st.session_state.get("cleaning_original_df")
        if isinstance(original, pd.DataFrame):
            push_cleaning_history()
            st.session_state.cleaning_df = original.copy(deep=True).reset_index(drop=True)
            st.session_state.cleaning_revision = int(st.session_state.get("cleaning_revision", 0)) + 1
            st.rerun()
    top3.caption("Undo stores up to the last 15 cleaning operations. The original uploaded data is kept separately.")

    st.markdown("#### Edit the table")
    if len(df) > 5000:
        edit_full = st.checkbox("Edit the full dataset (may be slower)", value=False)
    else:
        edit_full = True

    if edit_full:
        edited = st.data_editor(
            df,
            num_rows="dynamic",
            use_container_width=True,
            height=430,
            key=f"cleaning_editor_{st.session_state.get('cleaning_revision', 0)}",
        )
        if not edited.equals(df):
            push_cleaning_history()
            st.session_state.cleaning_df = edited.reset_index(drop=True).copy()
            df = st.session_state.cleaning_df
    else:
        st.info("Showing a preview only. Enable full editing above to change cells or add/delete rows.")
        st.dataframe(df.head(1000), use_container_width=True, height=430)

    st.caption("Tip: the editable table itself can add or delete rows. The tools below give you more controlled cleaning actions.")

    with st.expander("➕ Rows & columns", expanded=False):
        c1, c2 = st.columns(2)
        if c1.button("+ Add blank row", use_container_width=True):
            new_row = pd.DataFrame([{c: "" for c in df.columns}])
            set_cleaning_df(pd.concat([df, new_row], ignore_index=True))
            st.rerun()

        delete_text = c2.text_input("Delete row number(s)", placeholder="Example: 2,5,8-12", help="Uses 1-based row numbers shown by position.")
        if c2.button("Delete specified rows", use_container_width=True):
            rows = parse_row_numbers(delete_text, len(df))
            if rows:
                indices = [r - 1 for r in rows]
                set_cleaning_df(df.drop(index=indices).reset_index(drop=True))
                st.rerun()
            else:
                st.warning("Enter valid row numbers, for example 2,5,8-12.")

        st.markdown("**Add a column**")
        ac1, ac2, ac3 = st.columns([2, 2, 1])
        new_col = ac1.text_input("New column name", key="new_column_name")
        default_val = ac2.text_input("Default value (optional)", key="new_column_default")
        if ac3.button("Add column", use_container_width=True):
            name = new_col.strip()
            if not name:
                st.warning("Enter a column name.")
            elif name in df.columns:
                st.warning("That column already exists.")
            else:
                out = df.copy()
                out[name] = default_val
                set_cleaning_df(out)
                st.rerun()

        if len(df.columns):
            st.markdown("**Rename / delete columns**")
            rc1, rc2, rc3 = st.columns([2, 2, 1])
            old_col = rc1.selectbox("Column to rename", list(df.columns), key="rename_old")
            new_name = rc2.text_input("New name", key="rename_new")
            if rc3.button("Rename", use_container_width=True):
                name = new_name.strip()
                if not name:
                    st.warning("Enter a new name.")
                elif name != old_col and name in df.columns:
                    st.warning("A column with that name already exists.")
                else:
                    set_cleaning_df(df.rename(columns={old_col: name}))
                    st.rerun()

            del_cols = st.multiselect("Columns to delete", list(df.columns), key="columns_to_delete")
            if st.button("Delete selected columns", disabled=not del_cols):
                if len(del_cols) >= len(df.columns):
                    st.warning("Keep at least one column in the dataset.")
                else:
                    set_cleaning_df(df.drop(columns=del_cols))
                    st.rerun()

    with st.expander("🧩 Missing values", expanded=True):
        report = missing_report(df)
        st.dataframe(report, use_container_width=True, hide_index=True, height=min(300, 42 + 35 * max(1, min(len(report), 7))))
        cols_with_missing = report.loc[report["Missing"] > 0, "Column"].tolist()
        selected_missing_cols = st.multiselect(
            "Columns to handle",
            list(df.columns),
            default=cols_with_missing,
            key="missing_columns",
        )
        mv1, mv2 = st.columns(2)
        strategy = mv1.selectbox(
            "Method",
            ["Automatic (numeric median, text mode)", "Mean", "Median", "Mode", "Custom value", "Drop rows with missing values"],
        )
        custom = mv2.text_input("Custom fill value", disabled=strategy != "Custom value")
        if st.button("Apply missing-value handling", type="primary", disabled=not selected_missing_cols):
            if strategy == "Drop rows with missing values":
                temp = normalize_missing_in_columns(df, selected_missing_cols)
                out = temp.dropna(subset=selected_missing_cols).reset_index(drop=True)
            else:
                out = fill_missing_values(df, selected_missing_cols, strategy, custom)
            set_cleaning_df(out)
            st.rerun()

        threshold = st.slider("Drop columns when missing values are at least this percentage", 10, 100, 80, 5)
        if st.button("Drop high-missing columns"):
            rep = missing_report(df)
            cols_to_drop = rep.loc[rep["Missing %"] >= threshold, "Column"].tolist()
            if cols_to_drop:
                set_cleaning_df(df.drop(columns=cols_to_drop))
                st.rerun()
            else:
                st.info("No columns meet that missing-value threshold.")

    with st.expander("🧹 Common cleaning", expanded=False):
        a1, a2, a3 = st.columns(3)
        remove_dups = a1.checkbox("Remove duplicate rows", value=True)
        trim_spaces = a2.checkbox("Trim extra spaces", value=True)
        remove_empty = a3.checkbox("Remove fully empty rows/columns", value=True)
        b1, b2 = st.columns(2)
        standardize_cols = b1.checkbox("Standardize column names to snake_case")
        reset_index = b2.checkbox("Reset row index", value=True)
        if st.button("Apply common cleaning"):
            out = df.copy()
            if trim_spaces:
                for col in out.select_dtypes(include=["object", "string"]).columns:
                    out[col] = out[col].map(lambda v: re.sub(r"\s+", " ", str(v)).strip() if pd.notna(v) else v)
            if remove_empty:
                temp = normalize_missing_in_columns(out, list(out.columns))
                out = temp.dropna(axis=0, how="all").dropna(axis=1, how="all")
            if remove_dups:
                out = out.drop_duplicates()
            if standardize_cols:
                names = []
                used = set()
                for c in out.columns:
                    base = re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") or "column"
                    name = base
                    i = 2
                    while name in used:
                        name = f"{base}_{i}"
                        i += 1
                    used.add(name)
                    names.append(name)
                out.columns = names
            if reset_index:
                out = out.reset_index(drop=True)
            set_cleaning_df(out)
            st.rerun()

    with st.expander("🔎 Find, replace & text cleanup", expanded=False):
        columns = list(df.columns)
        target_cols = st.multiselect("Target columns", columns, default=columns[:1] if columns else [], key="replace_cols")
        fr1, fr2 = st.columns(2)
        find_value = fr1.text_input("Find", key="find_value")
        replacement = fr2.text_input("Replace with", key="replace_value")
        use_regex = st.checkbox("Use regular expression", key="replace_regex")
        if st.button("Find & replace", disabled=not target_cols or find_value == ""):
            out = df.copy()
            for col in target_cols:
                if use_regex:
                    out[col] = out[col].astype("string").str.replace(find_value, replacement, regex=True)
                else:
                    out[col] = out[col].astype("string").str.replace(find_value, replacement, regex=False)
            set_cleaning_df(out)
            st.rerun()

        tc1, tc2 = st.columns(2)
        text_cols = [c for c in df.columns if pd.api.types.is_object_dtype(df[c].dtype) or pd.api.types.is_string_dtype(df[c].dtype)]
        case_cols = tc1.multiselect("Text columns", text_cols, key="case_cols")
        case_action = tc2.selectbox("Text case", ["Lowercase", "UPPERCASE", "Title Case"])
        if st.button("Apply text case", disabled=not case_cols):
            out = df.copy()
            for col in case_cols:
                s = out[col].astype("string")
                if case_action == "Lowercase":
                    out[col] = s.str.lower()
                elif case_action == "UPPERCASE":
                    out[col] = s.str.upper()
                else:
                    out[col] = s.str.title()
            set_cleaning_df(out)
            st.rerun()

        sc1, sc2 = st.columns(2)
        special_cols = sc1.multiselect("Remove special characters from", text_cols, key="special_cols")
        keep_chars = sc2.text_input("Characters to keep in addition to letters/numbers/spaces", value=".-_@", key="keep_chars")
        if st.button("Remove special characters", disabled=not special_cols):
            escaped = re.escape(keep_chars)
            pattern = rf"[^\w\s{escaped}]"
            out = df.copy()
            for col in special_cols:
                out[col] = out[col].astype("string").str.replace(pattern, "", regex=True)
            set_cleaning_df(out)
            st.rerun()

    with st.expander("🔢 Data types", expanded=False):
        if len(df.columns):
            dt1, dt2 = st.columns(2)
            dtype_col = dt1.selectbox("Column", list(df.columns), key="dtype_col")
            dtype_target = dt2.selectbox("Convert to", ["Text", "Integer", "Decimal", "Date", "Boolean"], key="dtype_target")
            if st.button("Convert data type"):
                out = df.copy()
                try:
                    if dtype_target == "Text":
                        out[dtype_col] = out[dtype_col].astype("string")
                    elif dtype_target == "Integer":
                        out[dtype_col] = pd.to_numeric(out[dtype_col], errors="coerce").round().astype("Int64")
                    elif dtype_target == "Decimal":
                        out[dtype_col] = pd.to_numeric(out[dtype_col], errors="coerce").astype("Float64")
                    elif dtype_target == "Date":
                        out[dtype_col] = pd.to_datetime(out[dtype_col], errors="coerce")
                    else:
                        out[dtype_col] = convert_boolean(out[dtype_col])
                    set_cleaning_df(out)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not convert the column: {exc}")

    with st.expander("🔗 Merge / split columns", expanded=False):
        if len(df.columns) >= 2:
            merge_cols = st.multiselect("Columns to merge", list(df.columns), key="merge_cols")
            mc1, mc2 = st.columns(2)
            merged_name = mc1.text_input("New merged column name", value="merged_column")
            separator = mc2.text_input("Separator", value=" ")
            if st.button("Merge selected columns", disabled=len(merge_cols) < 2):
                out = df.copy()
                out[merged_name.strip() or "merged_column"] = out[merge_cols].fillna("").astype(str).agg(separator.join, axis=1).str.strip()
                set_cleaning_df(out)
                st.rerun()

        if len(df.columns):
            sp1, sp2, sp3 = st.columns(3)
            split_col = sp1.selectbox("Column to split", list(df.columns), key="split_col")
            split_sep = sp2.text_input("Split separator", value=",", key="split_sep")
            split_prefix = sp3.text_input("New column prefix", value=f"{split_col}_part", key="split_prefix")
            if st.button("Split column"):
                if split_sep == "":
                    st.warning("Enter a separator.")
                else:
                    parts = df[split_col].astype("string").str.split(split_sep, expand=True)
                    out = df.copy()
                    for i in range(parts.shape[1]):
                        out[f"{split_prefix}_{i+1}"] = parts[i]
                    set_cleaning_df(out)
                    st.rerun()

    with st.expander("↕ Sort & filter rows", expanded=False):
        if len(df.columns):
            sf1, sf2 = st.columns(2)
            sort_col = sf1.selectbox("Sort by", list(df.columns), key="sort_col")
            ascending = sf2.selectbox("Order", ["Ascending", "Descending"]) == "Ascending"
            if st.button("Sort rows"):
                try:
                    set_cleaning_df(df.sort_values(sort_col, ascending=ascending, na_position="last"))
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not sort: {exc}")

            f1, f2, f3 = st.columns([2, 2, 2])
            filter_col = f1.selectbox("Filter column", list(df.columns), key="filter_col")
            operator = f2.selectbox("Condition", ["equals", "not equals", "contains", "does not contain", ">", ">=", "<", "<=", "is missing", "is not missing"], key="filter_op")
            filter_val = f3.text_input("Value", disabled=operator in ("is missing", "is not missing"), key="filter_val")
            if st.button("Apply filter"):
                series = df[filter_col]
                if operator == "is missing":
                    mask = missing_mask(series)
                elif operator == "is not missing":
                    mask = ~missing_mask(series)
                elif operator in (">", ">=", "<", "<="):
                    left = pd.to_numeric(series, errors="coerce")
                    try:
                        right = float(filter_val)
                    except ValueError:
                        st.warning("Enter a numeric filter value.")
                        right = None
                    if right is None:
                        mask = pd.Series(False, index=df.index)
                    elif operator == ">": mask = left > right
                    elif operator == ">=": mask = left >= right
                    elif operator == "<": mask = left < right
                    else: mask = left <= right
                else:
                    left = series.astype("string")
                    if operator == "equals": mask = left == filter_val
                    elif operator == "not equals": mask = left != filter_val
                    elif operator == "contains": mask = left.str.contains(filter_val, case=False, na=False, regex=False)
                    else: mask = ~left.str.contains(filter_val, case=False, na=False, regex=False)
                set_cleaning_df(df.loc[mask].reset_index(drop=True))
                st.rerun()

    with st.expander("📉 Numeric outliers (IQR)", expanded=False):
        numeric_candidates = [c for c in df.columns if is_numeric_like(df[c])]
        outlier_cols = st.multiselect("Numeric columns", numeric_candidates, key="outlier_cols")
        factor = st.slider("IQR multiplier", 1.0, 3.0, 1.5, 0.1)
        outlier_action = st.radio("Action", ["Remove rows outside limits", "Cap values to limits"], horizontal=True)
        if st.button("Apply outlier handling", disabled=not outlier_cols):
            out = df.copy()
            keep = pd.Series(True, index=out.index)
            for col in outlier_cols:
                values = pd.to_numeric(out[col], errors="coerce")
                q1, q3 = values.quantile(0.25), values.quantile(0.75)
                iqr = q3 - q1
                if pd.isna(iqr) or iqr == 0:
                    continue
                lower, upper = q1 - factor * iqr, q3 + factor * iqr
                if outlier_action == "Remove rows outside limits":
                    keep &= values.isna() | values.between(lower, upper)
                else:
                    out[col] = values.clip(lower, upper)
            if outlier_action == "Remove rows outside limits":
                out = out.loc[keep]
            set_cleaning_df(out.reset_index(drop=True))
            st.rerun()

    st.markdown("#### Cleaned dataset")
    current = st.session_state.get("cleaning_df", df)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows", len(current))
    c2.metric("Columns", len(current.columns))
    c3.metric("Missing cells", int(sum(int(missing_mask(current[c]).sum()) for c in current.columns)) if len(current.columns) else 0)
    c4.metric("Duplicates", int(current.duplicated().sum()) if len(current) else 0)

    csv_bytes, xlsx_bytes, json_bytes = make_downloads(current, prefix="datamate_cleaned")
    d1, d2, d3 = st.columns(3)
    d1.download_button("⬇ Download cleaned CSV", csv_bytes, "datamate_cleaned.csv", "text/csv", use_container_width=True)
    d2.download_button("⬇ Download cleaned Excel", xlsx_bytes, "datamate_cleaned.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    d3.download_button("⬇ Download cleaned JSON", json_bytes, "datamate_cleaned.json", "application/json", use_container_width=True)

# -----------------------------
# State
# -----------------------------
for key, default in {
    "source_text": "",
    "source_name": "",
    "source_df": None,
    "links": [],
    "result": None,
    "cleaning_df": None,
    "cleaning_original_df": None,
    "cleaning_source_id": "",
    "cleaning_history": [],
    "cleaning_revision": 0,
    "loaded_source_id": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# -----------------------------
# UI
# -----------------------------
st.markdown(
    """
    <style>
    /* Floating developer button */
    .st-key-developer_float {
        position: fixed;
        right: 26px;
        bottom: 22px;
        width: auto !important;
        z-index: 999999;
    }
    .st-key-developer_float button {
        border-radius: 999px !important;
        padding: 0.62rem 1.05rem !important;
        min-height: 48px !important;
        background: #111827 !important;
        border: 1px solid #334155 !important;
        color: #f8fafc !important;
        box-shadow: 0 12px 30px rgba(0,0,0,.24);
        font-weight: 700 !important;
    }
    .st-key-developer_float button:hover {
        border-color: #6366f1 !important;
        transform: translateY(-1px);
    }

    /* Developer popup styling — shaped like the right-side panel in the reference */
    div[data-testid="stDialog"] div[role="dialog"] {
        border: 1px solid #263449 !important;
        border-radius: 22px !important;
        box-shadow: 0 24px 70px rgba(0,0,0,.36) !important;
    }
    .developer-hero {
        display:flex; gap:18px; align-items:center; padding:4px 0 14px 0;
    }
    .developer-avatar {
        width:92px; height:92px; border-radius:50%; border:5px solid #6257ff;
        display:flex; align-items:center; justify-content:center; font-size:44px;
        background:#0f172a;
    }
    .developer-name { font-size:1.8rem; font-weight:800; line-height:1.15; }
    .developer-role { margin-top:7px; opacity:.82; }
    .online-dot {
        display:inline-block; width:10px; height:10px; border-radius:50%;
        background:#3b82f6; margin-right:8px;
    }
    .developer-card {
        border:1px solid #34445f; border-radius:16px; padding:18px 20px;
        background:rgba(30,41,59,.76); line-height:1.7; margin-bottom:12px;
    }
    .tech-tags { display:flex; flex-wrap:wrap; gap:10px; margin-bottom:12px; }
    .tech-tags span {
        border:1px solid #3a4a64; border-radius:999px; padding:8px 13px;
        background:#172238; font-weight:700; font-size:.92rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="developer_float"):
    if st.button("🟢  Developer", key="developer_button"):
        developer_dialog()

st.title("🤖 DataMate AI")
st.caption("One workspace for collecting, extracting, cleaning, analyzing and exporting data from links and files.")

with st.sidebar:
    st.header("Choose work area")
    task = st.radio("What do you want to do?", list(WORK_AREAS.keys()))
    st.caption(WORK_AREAS[task])
    st.divider()
    st.markdown("**Supported inputs**")
    st.write("PDF, CSV, Excel, TXT, JSON, website URL, or pasted text")
    st.markdown("**Exports**")
    st.write("CSV, Excel, JSON")

st.subheader("1. Add your source")
source_mode = st.radio(
    "Source type",
    ["Upload file", "Website URL", "Paste text"],
    horizontal=True,
)

if source_mode == "Upload file":
    uploaded = st.file_uploader(
        "Upload one file",
        type=["pdf", "csv", "xlsx", "xls", "txt", "json"],
    )
    if uploaded is not None:
        try:
            suffix = uploaded.name.lower().rsplit(".", 1)[-1]
            df = None
            text = ""
            if suffix == "pdf":
                text = read_pdf(uploaded)
            elif suffix == "csv":
                df = pd.read_csv(uploaded)
                text = dataframe_to_text(df)
            elif suffix in ("xlsx", "xls"):
                df = pd.read_excel(uploaded)
                text = dataframe_to_text(df)
            elif suffix == "json":
                raw = json.load(uploaded)
                if isinstance(raw, list):
                    df = pd.json_normalize(raw)
                elif isinstance(raw, dict):
                    try:
                        df = pd.json_normalize(raw)
                    except Exception:
                        df = pd.DataFrame([raw])
                text = json.dumps(raw, ensure_ascii=False, indent=2)
            else:
                text = uploaded.getvalue().decode("utf-8", errors="replace")

            st.session_state.source_text = text
            st.session_state.source_name = uploaded.name
            st.session_state.source_df = df
            st.session_state.links = []
            source_id = f"upload:{uploaded.name}:{getattr(uploaded, 'size', len(text))}"
            if st.session_state.get("loaded_source_id") != source_id:
                st.session_state.loaded_source_id = source_id
                if df is not None:
                    initialize_cleaning_workspace(df, source_id, force=True)
                else:
                    st.session_state.cleaning_df = None
                    st.session_state.cleaning_original_df = None
                    st.session_state.cleaning_history = []
                    st.session_state.cleaning_source_id = source_id
            st.success(f"Loaded {uploaded.name}")
        except Exception as exc:
            st.error(f"Could not read the file: {exc}")

elif source_mode == "Website URL":
    url = st.text_input("Public webpage URL", placeholder="https://example.com/page")
    if st.button("Load website", type="primary"):
        if not url.strip():
            st.warning("Enter a URL first.")
        else:
            try:
                text, links = read_web(url.strip())
                st.session_state.source_text = text
                st.session_state.source_name = url.strip()
                st.session_state.source_df = None
                st.session_state.links = links
                st.session_state.cleaning_df = None
                st.session_state.cleaning_original_df = None
                st.session_state.cleaning_history = []
                st.session_state.cleaning_source_id = f"url:{url.strip()}"
                st.session_state.loaded_source_id = f"url:{url.strip()}"
                st.success("Website loaded successfully.")
            except PermissionError as exc:
                st.warning(f"The website blocked automated access ({exc}).")
                st.info("Open the page in your browser, copy the relevant text, then use Paste text. DataMate does not bypass website protections.")
            except Exception as exc:
                st.error(f"Could not load the webpage: {exc}")

else:
    pasted = st.text_area("Paste text here", height=220)
    if st.button("Use pasted text", type="primary"):
        if pasted.strip():
            st.session_state.source_text = pasted
            st.session_state.source_name = "Pasted text"
            st.session_state.source_df = None
            st.session_state.links = []
            st.session_state.cleaning_df = None
            st.session_state.cleaning_original_df = None
            st.session_state.cleaning_history = []
            st.session_state.cleaning_source_id = "paste:Pasted text"
            st.session_state.loaded_source_id = "paste:Pasted text"
            st.success("Text loaded.")
        else:
            st.warning("Paste some text first.")

if st.session_state.source_text:
    st.divider()

    if task == "Data Cleaning" and isinstance(st.session_state.get("cleaning_df"), pd.DataFrame):
        render_cleaning_workspace()
    else:
        st.subheader("2. Configure the task")

        if task == "Data Cleaning" and st.session_state.source_df is None:
            st.info("PDF, URL and pasted text must first be converted into a table. Use Data Extraction, run it, then click ‘Open result in Data Cleaning’ below the result.")

        request = st.text_input(
            "Instruction",
            value="",
            placeholder="Example: Give me product name, price, phone, email and address",
        )

        source_df = st.session_state.source_df
        source_columns = [str(c) for c in source_df.columns] if source_df is not None else []

        default_fields = ["Name", "Email", "Phone", "Address"]
        if task in ("Product Listing", "E-commerce Data Entry"):
            default_fields = ["Product", "Price", "SKU", "Category", "Description"]

        preset = "standard"
        if source_columns:
            st.success(f"Detected {len(source_columns)} columns in your uploaded table. Every CSV/Excel/JSON column is available below.")
            with st.expander("View detected columns", expanded=False):
                st.write(source_columns)

            preset = st.selectbox(
                "Field preset",
                ["Choose manually", "All uploaded columns", "Bank / Loan", "Contact / Customer", "Product / E-commerce", "Financial / Transaction"],
                help="Presets only help you choose fields. You can still add or remove any field below.",
            )
            bank_keywords = ["loan", "credit", "income", "applicant", "coapplicant", "property", "depend", "education", "employ", "married", "gender", "status", "term", "amount", "interest", "dti", "emi"]
            contact_keywords = ["name", "email", "phone", "mobile", "address", "customer", "client", "age", "gender"]
            product_keywords = ["product", "item", "sku", "price", "category", "description", "brand", "stock", "quantity"]
            financial_keywords = ["account", "transaction", "balance", "amount", "date", "bank", "branch", "debit", "credit"]

            def preset_columns(keywords):
                return [c for c in source_columns if any(k in normalize_field_name(c) for k in keywords)]

            if preset == "All uploaded columns":
                default_fields = source_columns
            elif preset == "Bank / Loan":
                default_fields = preset_columns(bank_keywords) or source_columns[: min(10, len(source_columns))]
            elif preset == "Contact / Customer":
                default_fields = preset_columns(contact_keywords) or source_columns[: min(8, len(source_columns))]
            elif preset == "Product / E-commerce":
                default_fields = preset_columns(product_keywords) or source_columns[: min(8, len(source_columns))]
            elif preset == "Financial / Transaction":
                default_fields = preset_columns(financial_keywords) or source_columns[: min(8, len(source_columns))]
            else:
                default_fields = source_columns[: min(8, len(source_columns))]

            field_options = source_columns + [f for f in PATTERNS.keys() if f not in source_columns]
        else:
            field_options = list(PATTERNS.keys())

        selected_fields = st.multiselect(
            "Fields to extract",
            field_options,
            default=[f for f in default_fields if f in field_options],
            key=f"selected_fields::{st.session_state.source_name}::{preset}",
            help="For CSV/Excel/JSON, your real column names appear first. For PDFs, URLs and text, choose standard extraction fields.",
        )

        with st.expander("Optional local AI (Ollama)"):
            use_ai = st.checkbox("Use Ollama for smarter extraction")
            model = st.text_input("Model", "llama3.2")
            endpoint = st.text_input("Endpoint", "http://localhost:11434")

        if task != "Data Cleaning" and st.button("Run DataMate", type="primary", use_container_width=True):
            try:
                source_df = st.session_state.source_df
                source_text = st.session_state.source_text

                if task == "Data Formatting":
                    if source_df is None:
                        st.warning("Data Formatting works best with CSV/Excel/JSON table data.")
                        result = extract_records(source_text, selected_fields)
                    else:
                        result = clean_dataframe(source_df)

                elif task == "Data Analysis":
                    if source_df is None:
                        extracted = extract_records(source_text, selected_fields)
                        result = quick_analysis(extracted)
                    else:
                        result = quick_analysis(source_df)

                elif task == "Data Scraping":
                    if st.session_state.links:
                        result = pd.DataFrame(st.session_state.links).drop_duplicates().reset_index(drop=True)
                    else:
                        fields = resolve_fields(request, selected_fields, source_df)
                        result = extract_records(source_text, fields)

                elif task == "Data Mining":
                    if source_df is not None:
                        fields = resolve_fields(request, selected_fields, source_df)
                        selected_table = select_dataframe_fields(source_df, fields)
                        result = clean_dataframe(selected_table if not selected_table.empty else source_df)
                    else:
                        fields = resolve_fields(request, selected_fields, source_df)
                        result = extract_records(source_text, fields)

                else:
                    fields = resolve_fields(request, selected_fields, source_df)
                    if not fields:
                        st.warning("Choose at least one field or describe the fields in your instruction.")
                        st.stop()

                    if source_df is not None:
                        table_result = select_dataframe_fields(source_df, fields)
                        if not table_result.empty:
                            result = table_result
                        elif use_ai:
                            result = ollama_extract(source_text, request or ", ".join(fields), model, endpoint)
                        else:
                            result = extract_records(source_text, fields)
                    elif use_ai:
                        result = ollama_extract(source_text, request or ", ".join(fields), model, endpoint)
                    else:
                        result = extract_records(source_text, fields)

                st.session_state.result = result
                if result is None or result.empty:
                    st.warning("No matching information found.")
                else:
                    st.success("Task completed.")
            except requests.exceptions.ConnectionError:
                st.error("Could not connect to Ollama. Start Ollama or turn the option off.")
            except Exception as exc:
                st.error(f"Processing failed: {exc}")

if st.session_state.result is not None and task != "Data Cleaning":
    st.divider()
    st.subheader("3. Results")
    result = st.session_state.result
    st.dataframe(result, use_container_width=True, height=380)

    m1, m2, m3 = st.columns(3)
    m1.metric("Rows", len(result))
    m2.metric("Columns", len(result.columns))
    m3.metric("Task", task)

    csv_bytes, xlsx_bytes, json_bytes = make_downloads(result)
    d1, d2, d3 = st.columns(3)
    d1.download_button("⬇ Download CSV", csv_bytes, "datamate_result.csv", "text/csv", use_container_width=True)
    d2.download_button("⬇ Download Excel", xlsx_bytes, "datamate_result.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    d3.download_button("⬇ Download JSON", json_bytes, "datamate_result.json", "application/json", use_container_width=True)

    if st.button("🧹 Open this result in Data Cleaning", use_container_width=True):
        initialize_cleaning_workspace(result, f"result:{st.session_state.source_name}:{len(result)}:{len(result.columns)}", force=True)
        st.success("Result loaded into the Data Cleaning workspace. Choose Data Cleaning from the sidebar.")

if st.session_state.source_text:
    st.divider()
    with st.expander("Preview loaded source"):
        if st.session_state.source_df is not None:
            st.dataframe(st.session_state.source_df.head(300), use_container_width=True)
        else:
            st.text_area("Source preview", st.session_state.source_text[:25000], height=350, disabled=True)

    if st.session_state.links:
        with st.expander(f"Links found ({len(st.session_state.links)})"):
            st.dataframe(pd.DataFrame(st.session_state.links).head(500), use_container_width=True)

st.divider()
st.subheader("DataMate AI work areas")
cols = st.columns(4)
for i, (name, desc) in enumerate(WORK_AREAS.items()):
    with cols[i % 4]:
        st.markdown(f"### {name}")
        st.caption(desc)

st.info("Use public or authorized data only. Respect website terms, privacy, robots rules and rate limits.")
