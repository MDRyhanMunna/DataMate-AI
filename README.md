# DataMate AI

**DataMate AI** is a Streamlit data-work assistant for collecting, extracting, cleaning, formatting, analyzing, and exporting data from files, public webpages, and pasted text.

The visible app name remains **DataMate AI**. This package is the **v4.4** update.

## Supported inputs

- PDF
- CSV
- Excel (`.xlsx`, `.xls`)
- JSON
- TXT
- Public webpage URL
- Pasted text

## Work areas

1. Data Mining
2. Data Formatting
3. **Data Cleaning**
4. Data Scraping
5. Data Extraction
6. Data Collection
7. Data Analysis
8. Product Listing
9. E-commerce Data Entry

## New in v4.4 — interactive Data Cleaning workspace

For CSV, Excel, and JSON data, choose **Data Cleaning** from the sidebar. DataMate now provides an editable workspace with:

- Direct cell editing
- Add blank rows
- Delete rows
- Add columns with optional default values
- Rename columns
- Delete selected columns
- Missing-value report with count and percentage
- Missing-value handling:
  - Automatic: numeric → median, text/categorical → mode
  - Mean
  - Median
  - Mode
  - Custom value
  - Drop rows with missing values
  - Drop columns above a chosen missing-value percentage
- Remove duplicate rows
- Trim extra spaces
- Remove fully empty rows/columns
- Standardize column names to `snake_case`
- Find and replace
- Lowercase / uppercase / title case
- Remove unwanted special characters
- Convert column type to text, integer, decimal, date, or boolean
- Merge multiple columns
- Split a column using a separator
- Sort rows
- Filter rows with text, numeric, and missing-value conditions
- IQR-based numeric outlier handling:
  - Remove outlier rows
  - Cap values to IQR limits
- Undo up to the last 15 cleaning operations
- Reset to the original uploaded dataset
- Download the cleaned data as CSV, Excel, or JSON

For a PDF, webpage, or pasted text, first run **Data Extraction** (or another extraction task), then use **Open this result in Data Cleaning** under the result table.

## Smart field selection

For CSV, Excel, and JSON files, DataMate automatically detects the real column names and adds every column to **Fields to extract**.

For example, a bank-loan dataset can expose fields such as:

- `Loan_ID`
- `ApplicantIncome`
- `CoapplicantIncome`
- `LoanAmount`
- `Loan_Amount_Term`
- `Credit_History`
- `Property_Area`
- `Loan_Status`

Field presets include:

- All uploaded columns
- Bank / Loan
- Contact / Customer
- Product / E-commerce
- Financial / Transaction

## Developer panel

A floating **Developer** button appears at the bottom-right of the app. It opens a developer panel with:

- Developer name and role
- About section
- Technologies used
- GitHub link
- Portfolio link
- Contact form
- EmailJS message delivery

Configured GitHub profile:

`https://github.com/MDRyhanMunna`

## EmailJS

The supplied EmailJS Service ID, Template ID, and Public Key are configured in the project. A Private Key is not required for the normal contact-form setup.

The EmailJS template should use these variables:

- `{{from_name}}`
- `{{from_email}}`
- `{{reply_to}}`
- `{{message}}`
- `{{to_name}}`
- `{{project_name}}`

You can override the built-in configuration by copying `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and editing the values.

## Installation on Windows

Open PowerShell or Command Prompt inside the project folder and run:

```powershell
python -m venv venv
.\venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Using `python -m streamlit` avoids the common **'streamlit is not recognized'** PATH error.

### Easier option

Double-click `run_datamate.bat`. In v4.4 the batch file can create the virtual environment, install the requirements, and start DataMate AI automatically.

## Website note

Some websites block automated requests with 401/403/429 responses. DataMate does not bypass those protections. For a blocked page, open it in your browser, copy the relevant text, and use **Paste text** instead.
