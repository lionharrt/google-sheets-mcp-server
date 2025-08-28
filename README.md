# Google Sheets MCP Server

A Model Context Protocol (MCP) server that provides Google Sheets integration with HTTP+Streamable transport for Dify and other MCP clients.

## Features

- ✅ **Streamable HTTP Transport**: Modern MCP transport for Dify integration
- ✅ **Google Sheets API Integration**: Full CRUD operations on spreadsheets
- ✅ **Multiple Authentication Methods**: Service Account, OAuth, ADC support
- ✅ **Cloud-Ready**: Containerized for Google Cloud Run deployment
- ✅ **Production Logging**: Structured logging with proper error handling

## Available Tools

- `get_sheet_data` - Read data from spreadsheet ranges
- `update_cells` - Update specific cell ranges
- `create_spreadsheet` - Create new spreadsheets
- `list_spreadsheets` - List available spreadsheets
- `add_rows` - Append rows to sheets
- `list_sheets` - List sheets within a spreadsheet
- `create_sheet` - Add new sheet tabs
- `health_check` - Server health monitoring

## Quick Start

### 1. Prerequisites

- Python 3.10+
- Google Cloud Project with Sheets and Drive APIs enabled
- Service account credentials

### 2. Installation

```bash
git clone https://github.com/lionharrt/google-sheets-mcp-server.git
cd google-sheets-mcp-server
pip install -e .
```

### 3. Authentication Setup

#### Option A: Service Account (Recommended)

1. Create a service account in Google Cloud Console
2. Download the JSON key file as `service-account-key.json`
3. Create a Google Drive folder and share it with the service account email
4. Set environment variables:

```bash
export SERVICE_ACCOUNT_PATH=service-account-key.json
export DRIVE_FOLDER_ID=your_google_drive_folder_id
```

#### Option B: OAuth (Development)

1. Download OAuth credentials as `credentials.json`
2. Set environment variables:

```bash
export CREDENTIALS_PATH=credentials.json
export TOKEN_PATH=token.json
```

### 4. Run the Server

```bash
python -m google_sheets_mcp_server
```

The server will start on `http://0.0.0.0:8000` with:
- Streamable HTTP endpoint: `/mcp`
- SSE endpoint: `/sse` (backward compatibility)

## Deployment

### Docker

```bash
docker build -t google-sheets-mcp-server .
docker run -p 8000:8000 \
  -e SERVICE_ACCOUNT_PATH=service-account-key.json \
  -e DRIVE_FOLDER_ID=your_folder_id \
  google-sheets-mcp-server
```

### Google Cloud Run

```bash
# Build and push to Container Registry
gcloud builds submit --tag gcr.io/your-project/google-sheets-mcp-server

# Deploy to Cloud Run
gcloud run deploy google-sheets-mcp-server \
  --image gcr.io/your-project/google-sheets-mcp-server \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars SERVICE_ACCOUNT_PATH=service-account-key.json,DRIVE_FOLDER_ID=your_folder_id
```

## Dify Integration

1. Deploy the MCP server to a publicly accessible URL
2. In Dify, go to Tools → MCP
3. Add MCP Server (HTTP) with:
   - **Server URL**: `https://your-server-url/mcp`
   - **Name**: `Google Sheets`
   - **Server Identifier**: `google-sheets-mcp`

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `SERVICE_ACCOUNT_PATH` | Path to service account JSON key | Yes* |
| `DRIVE_FOLDER_ID` | Google Drive folder ID for spreadsheets | Yes* |
| `CREDENTIALS_PATH` | Path to OAuth credentials JSON | Yes* |
| `TOKEN_PATH` | Path to store OAuth token | No |
| `CREDENTIALS_CONFIG` | Base64 encoded service account JSON | Yes* |
| `PORT` | Server port (default: 8000) | No |
| `DEBUG` | Enable debug logging (default: false) | No |

*One authentication method required

## Security Notes

- Never commit authentication files to version control
- Use service accounts for production deployments
- Restrict Google Drive folder access to necessary users
- Enable HTTPS for production deployments

## Troubleshooting

### Authentication Issues

1. Verify service account has Editor role
2. Check Google Drive folder is shared with service account email
3. Ensure APIs are enabled in Google Cloud Console

### Connection Issues

1. Verify server is accessible on the configured port
2. Check firewall settings for cloud deployments
3. Confirm MCP endpoint paths are correct

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Code Quality

```bash
# Format code
black src/
isort src/

# Type checking
mypy src/

# Linting
flake8 src/
```

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review Google Sheets API documentation
3. Open an issue on GitHub
