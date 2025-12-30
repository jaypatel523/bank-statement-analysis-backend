# Bank Statement API

This project provides a FastAPI application that converts bank PDF statements into CSV format. Users can upload their bank statements through a web interface, and the application processes these files to generate downloadable CSV files.

## Project Structure

```
bank-statement-api
├── src
│   ├── main.py                # Entry point of the application
│   ├── api
│   │   └── v1
│   │       └── endpoints.py   # API endpoints for handling requests
│   ├── services
│   │   └── converter.py       # Logic for converting PDF to CSV
│   ├── models
│   │   └── schemas.py         # Data models and schemas for validation
│   └── core
│       └── config.py          # Configuration settings for the application
├── tests
│   └── test_upload.py         # Unit tests for the upload functionality
├── requirements.txt           # Project dependencies
├── .gitignore                 # Files and directories to ignore in Git
└── README.md                  # Project documentation
```

## Setup Instructions

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd bank-statement-api
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**:
   ```bash
   uvicorn src.main:app --reload
   ```

5. **Access the API**:
   Open your browser and navigate to `http://localhost:8000/docs` to view the API documentation and test the endpoints.

## Usage

- Select your bank and upload a PDF statement.
- If the PDF is password protected, provide the password.
- Click on "Upload & Convert" to process the file.
- A link to download the resulting CSV will be provided upon successful conversion.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.