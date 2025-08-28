#!/usr/bin/env python3
"""
Google Sheets MCP Server with HTTP+Streamable transport for Dify integration.

This server implements the Model Context Protocol (MCP) over HTTP with Streamable transport,
providing Google Sheets integration capabilities for Dify and other MCP clients.
"""

import base64
import os
import json
import logging
import hashlib
import secrets
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

# MCP imports
from mcp.server.fastmcp import FastMCP, Context

# HTTP imports for simple validation
from typing import Dict, Any, Optional

# Google API imports
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import google.auth

# Configuration and logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
CREDENTIALS_CONFIG = os.environ.get('CREDENTIALS_CONFIG')
TOKEN_PATH = os.environ.get('TOKEN_PATH', 'token.json')
CREDENTIALS_PATH = os.environ.get('CREDENTIALS_PATH', 'credentials.json')
SERVICE_ACCOUNT_PATH = os.environ.get('SERVICE_ACCOUNT_PATH', 'service-account-key.json')
DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID', '')  # Working directory in Google Drive

# API Key for authentication
API_KEY = os.environ.get('MCP_API_KEY')
if not API_KEY:
    # Generate a secure API key if not provided
    API_KEY = secrets.token_urlsafe(32)
    logger.warning(f"No MCP_API_KEY provided. Generated temporary key: {API_KEY}")
    logger.warning("Set MCP_API_KEY environment variable for production use")


@dataclass
class SpreadsheetContext:
    """Context for Google Spreadsheet service"""
    sheets_service: Any
    drive_service: Any
    folder_id: Optional[str] = None


# Simple authentication helper
def validate_api_key(provided_key: str) -> bool:
    """Validate API key using secure comparison"""
    if not provided_key or not API_KEY:
        return False
    return secrets.compare_digest(provided_key, API_KEY)


@asynccontextmanager
async def spreadsheet_lifespan(server: FastMCP) -> AsyncIterator[SpreadsheetContext]:
    """Manage Google Spreadsheet API connection lifecycle"""
    logger.info("Initializing Google Spreadsheet services...")
    
    # Authenticate and build the service
    creds = None

    # Priority 1: Check for base64 encoded credentials in environment
    if CREDENTIALS_CONFIG:
        try:
            creds_data = json.loads(base64.b64decode(CREDENTIALS_CONFIG))
            creds = service_account.Credentials.from_service_account_info(creds_data, scopes=SCOPES)
            logger.info("Using base64 encoded service account credentials")
        except Exception as e:
            logger.error(f"Error decoding CREDENTIALS_CONFIG: {e}")
            creds = None
    
    # Priority 2: Check for explicit service account file
    logger.info(f"Checking service account path: {SERVICE_ACCOUNT_PATH}")
    logger.info(f"File exists: {os.path.exists(SERVICE_ACCOUNT_PATH) if SERVICE_ACCOUNT_PATH else False}")
    
    if not creds and SERVICE_ACCOUNT_PATH and os.path.exists(SERVICE_ACCOUNT_PATH):
        try:
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_PATH,
                scopes=SCOPES
            )
            logger.info(f"Successfully loaded service account from file: {SERVICE_ACCOUNT_PATH}")
            logger.info(f"Working with Google Drive folder ID: {DRIVE_FOLDER_ID or 'Not specified'}")
        except Exception as e:
            logger.error(f"Error using service account file: {e}")
            creds = None
    
    # Priority 3: Fall back to OAuth flow if service account auth failed
    if not creds:
        logger.info("Attempting OAuth authentication flow")
        if os.path.exists(TOKEN_PATH):
            try:
                with open(TOKEN_PATH, 'r') as token:
                    creds = Credentials.from_authorized_user_info(json.load(token), SCOPES)
                logger.info("Loaded existing OAuth token")
            except Exception as e:
                logger.error(f"Error loading OAuth token: {e}")
                
        # If credentials are not valid or don't exist, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Refreshed OAuth token")
                except Exception as e:
                    logger.error(f"Error refreshing OAuth token: {e}")
                    creds = None
            
            if not creds:
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
                    creds = flow.run_local_server(port=0)
                    logger.info("Completed interactive OAuth flow")
                    
                    # Save the credentials for the next run
                    with open(TOKEN_PATH, 'w') as token:
                        token.write(creds.to_json())
                    logger.info(f"Saved OAuth credentials to {TOKEN_PATH}")
                except Exception as e:
                    logger.error(f"Error with OAuth flow: {e}")
                    creds = None
    
    # Priority 4: Try Application Default Credentials as final fallback
    if not creds:
        try:
            logger.info("Attempting to use Application Default Credentials (ADC)")
            creds, project = google.auth.default(scopes=SCOPES)
            logger.info(f"Successfully authenticated using ADC for project: {project}")
        except Exception as e:
            logger.error(f"Error using Application Default Credentials: {e}")
            raise Exception("All authentication methods failed. Please configure credentials.")
    
    # Build the services
    try:
        sheets_service = build('sheets', 'v4', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)
        logger.info("Successfully built Google API services")
    except Exception as e:
        logger.error(f"Error building Google API services: {e}")
        raise
    
    try:
        # Provide the service in the context
        yield SpreadsheetContext(
            sheets_service=sheets_service,
            drive_service=drive_service,
            folder_id=DRIVE_FOLDER_ID if DRIVE_FOLDER_ID else None
        )
        logger.info("Google Spreadsheet services initialized successfully")
    finally:
        # No explicit cleanup needed for Google APIs
        logger.info("Cleaning up Google Spreadsheet services")


# Initialize the MCP server with HTTP+Streamable transport
mcp = FastMCP(
    name="Google Sheets MCP Server",
    dependencies=["google-auth", "google-auth-oauthlib", "google-api-python-client"],
    lifespan=spreadsheet_lifespan,
    # Enable HTTP server with Streamable HTTP transport
    host="0.0.0.0",  # Listen on all interfaces for cloud deployment
    port=int(os.environ.get("PORT", 8000)),  # Use PORT env var for cloud deployment
    # Streamable HTTP path for MCP communication
    streamable_http_path="/mcp",
    # Also enable SSE path for backward compatibility
    sse_path="/sse",
    # Enable JSON response mode for debugging
    json_response=True,
    # Additional debugging
    debug=os.environ.get("DEBUG", "false").lower() == "true"
)

# Add a simple health check endpoint 
@mcp.tool()
def health_check() -> Dict[str, Any]:
    """Health check endpoint"""
    return {"status": "healthy", "service": "Google Sheets MCP Server"}

# Log authentication setup
logger.info("API Key authentication will be handled at deployment level")
logger.info(f"For direct access, use X-API-Key header with value: {API_KEY}")


# Google Sheets tools implementation
@mcp.tool()
def get_sheet_data(spreadsheet_id: str, 
                   sheet: str,
                   range: Optional[str] = None,
                   include_grid_data: bool = False,
                   ctx: Context = None) -> Dict[str, Any]:
    """
    Get data from a specific sheet in a Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        sheet: The name of the sheet
        range: Optional cell range in A1 notation (e.g., 'A1:C10'). If not provided, gets all data.
        include_grid_data: If True, includes cell formatting and other metadata in the response.
            Note: Setting this to True will significantly increase the response size and token usage
            when parsing the response, as it includes detailed cell formatting information.
            Default is False (returns values only, more efficient).
    
    Returns:
        Grid data structure with either full metadata or just values from Google Sheets API, depending on include_grid_data parameter
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service

    # Construct the range - keep original API behavior
    if range:
        full_range = f"{sheet}!{range}"
    else:
        full_range = sheet
    
    try:
        if include_grid_data:
            # Use full API to get all grid data including formatting
            result = sheets_service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                ranges=[full_range],
                includeGridData=True
            ).execute()
        else:
            # Use values API to get cell values only (more efficient)
            values_result = sheets_service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=full_range
            ).execute()
            
            # Format the response to match expected structure
            result = {
                'spreadsheetId': spreadsheet_id,
                'valueRanges': [{
                    'range': full_range,
                    'values': values_result.get('values', [])
                }]
            }

        logger.info(f"Successfully retrieved data from {spreadsheet_id}, sheet: {sheet}, range: {range or 'all'}")
        return result
    except Exception as e:
        logger.error(f"Error getting sheet data: {e}")
        raise


@mcp.tool()
def update_cells(spreadsheet_id: str,
                sheet: str,
                range: str,
                data: List[List[Any]],
                ctx: Context = None) -> Dict[str, Any]:
    """
    Update cells in a Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        sheet: The name of the sheet
        range: Cell range in A1 notation (e.g., 'A1:C10')
        data: 2D array of values to update
    
    Returns:
        Result of the update operation
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service
    
    # Construct the range
    full_range = f"{sheet}!{range}"
    
    # Prepare the value range object
    value_range_body = {
        'values': data
    }
    
    try:
        # Call the Sheets API to update values
        result = sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=full_range,
            valueInputOption='USER_ENTERED',
            body=value_range_body
        ).execute()
        
        logger.info(f"Successfully updated cells in {spreadsheet_id}, sheet: {sheet}, range: {range}")
        return result
    except Exception as e:
        logger.error(f"Error updating cells: {e}")
        raise


@mcp.tool()
def create_spreadsheet(title: str, ctx: Context = None) -> Dict[str, Any]:
    """
    Create a new Google Spreadsheet.
    
    Args:
        title: The title of the new spreadsheet
    
    Returns:
        Information about the newly created spreadsheet including its ID
    """
    drive_service = ctx.request_context.lifespan_context.drive_service
    folder_id = ctx.request_context.lifespan_context.folder_id

    # Create the spreadsheet
    file_body = {
        'name': title,
        'mimeType': 'application/vnd.google-apps.spreadsheet',
    }
    if folder_id:
        file_body['parents'] = [folder_id]
    
    try:
        spreadsheet = drive_service.files().create(
            supportsAllDrives=True,
            body=file_body,
            fields='id, name, parents'
        ).execute()

        spreadsheet_id = spreadsheet.get('id')
        parents = spreadsheet.get('parents')
        
        logger.info(f"Created spreadsheet '{title}' with ID: {spreadsheet_id}")

        return {
            'spreadsheetId': spreadsheet_id,
            'title': spreadsheet.get('name', title),
            'folder': parents[0] if parents else 'root',
        }
    except Exception as e:
        logger.error(f"Error creating spreadsheet: {e}")
        raise


@mcp.tool()
def list_spreadsheets(ctx: Context = None) -> List[Dict[str, str]]:
    """
    List all spreadsheets in the configured Google Drive folder.
    If no folder is configured, lists spreadsheets from 'My Drive'.
    
    Returns:
        List of spreadsheets with their ID and title
    """
    drive_service = ctx.request_context.lifespan_context.drive_service
    folder_id = ctx.request_context.lifespan_context.folder_id
    
    query = "mimeType='application/vnd.google-apps.spreadsheet'"
    
    # If a specific folder is configured, search only in that folder
    if folder_id:
        query += f" and '{folder_id}' in parents"
        logger.info(f"Searching for spreadsheets in folder: {folder_id}")
    else:
        logger.info("Searching for spreadsheets in 'My Drive'")
    
    try:
        # List spreadsheets
        results = drive_service.files().list(
            q=query,
            spaces='drive',
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
            fields='files(id, name)',
            orderBy='modifiedTime desc'
        ).execute()
        
        spreadsheets = results.get('files', [])
        
        logger.info(f"Found {len(spreadsheets)} spreadsheets")
        return [{'id': sheet['id'], 'title': sheet['name']} for sheet in spreadsheets]
    except Exception as e:
        logger.error(f"Error listing spreadsheets: {e}")
        raise


@mcp.tool()
def add_rows(spreadsheet_id: str,
             sheet: str,
             data: List[List[Any]],
             ctx: Context = None) -> Dict[str, Any]:
    """
    Append rows to the end of a sheet (after the last row with data).
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
        sheet: The name of the sheet
        data: 2D array of rows to append
    
    Returns:
        Result of the append operation
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service
    
    # Prepare the value range object
    value_range_body = {
        'values': data
    }
    
    try:
        # Call the Sheets API to append values
        result = sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=sheet,
            valueInputOption='USER_ENTERED',
            body=value_range_body
        ).execute()
        
        logger.info(f"Successfully added {len(data)} rows to {spreadsheet_id}, sheet: {sheet}")
        return result
    except Exception as e:
        logger.error(f"Error adding rows: {e}")
        raise


@mcp.tool()
def list_sheets(spreadsheet_id: str, ctx: Context = None) -> List[str]:
    """
    List all sheets in a Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet (found in the URL)
    
    Returns:
        List of sheet names
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service
    
    try:
        # Get spreadsheet metadata
        spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        
        # Extract sheet names
        sheet_names = [sheet['properties']['title'] for sheet in spreadsheet['sheets']]
        
        logger.info(f"Found {len(sheet_names)} sheets in spreadsheet {spreadsheet_id}")
        return sheet_names
    except Exception as e:
        logger.error(f"Error listing sheets: {e}")
        raise


@mcp.tool()
def create_sheet(spreadsheet_id: str, 
                title: str, 
                ctx: Context = None) -> Dict[str, Any]:
    """
    Create a new sheet tab in an existing Google Spreadsheet.
    
    Args:
        spreadsheet_id: The ID of the spreadsheet
        title: The title for the new sheet
    
    Returns:
        Information about the newly created sheet
    """
    sheets_service = ctx.request_context.lifespan_context.sheets_service
    
    # Define the add sheet request
    request_body = {
        "requests": [
            {
                "addSheet": {
                    "properties": {
                        "title": title
                    }
                }
            }
        ]
    }
    
    try:
        # Execute the request
        result = sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=request_body
        ).execute()
        
        # Extract the new sheet information
        new_sheet_props = result['replies'][0]['addSheet']['properties']
        
        logger.info(f"Created new sheet '{title}' in spreadsheet {spreadsheet_id}")
        return {
            'sheetId': new_sheet_props['sheetId'],
            'title': new_sheet_props['title'],
            'index': new_sheet_props.get('index'),
            'spreadsheetId': spreadsheet_id
        }
    except Exception as e:
        logger.error(f"Error creating sheet: {e}")
        raise


# Health check endpoint for deployment
@mcp.tool()
def health_check() -> Dict[str, str]:
    """
    Health check endpoint for deployment monitoring.
    
    Returns:
        Status information about the server
    """
    return {
        "status": "healthy",
        "service": "Google Sheets MCP Server",
        "version": "1.0.0"
    }


def main():
    """Main entry point for the server."""
    logger.info("Starting Google Sheets MCP Server with HTTP+Streamable transport")
    logger.info(f"Server will listen on 0.0.0.0:{os.environ.get('PORT', 8000)}")
    logger.info("Streamable HTTP endpoint: /mcp")
    logger.info("SSE endpoint: /sse")
    
    # Run the server in streamable HTTP mode
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
