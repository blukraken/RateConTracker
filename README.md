# RateCon Tracker: A Streamlit Application

## Introduction

This repository contains the source code for the RateCon Tracker, a sophisticated web application developed with the Streamlit framework. This application automates the processing of freight rate confirmations by parsing PDF files, extracting critical data, and presenting the aggregated information in an interactive dashboard. All extracted data is systematically archived in a centralized Google Sheet, which serves as a robust backend for streamlined data access and management.

## Core Capabilities

The application's core capabilities include:

* **Automated PDF Data Extraction:** Parses various RateCon document formats to automatically extract pertinent data fields such as reference numbers, financial rates, equipment specifications, and container numbers.
* **Data Visualization and Analytics:** Features an interactive dashboard for the visualization of key performance indicators (KPIs), including total revenue, aggregate load counts, and detailed revenue breakdowns.
* **Centralized Data Repository:** Utilizes Google Sheets as a centralized and reliable data repository, ensuring data integrity and establishing a single source of truth.
* **Data Integrity and Validation:** Incorporates a validation mechanism to prevent the processing of duplicate records by cross-referencing filenames and unique reference numbers.
* **Data Export Functionality:** Provides users with the capability to export the complete dataset into standard file formats, including Excel (`.xlsx`) and CSV, for offline analysis.
* **User Interface Design:** Designed with a clean, professional, and responsive user interface to ensure optimal usability and accessibility across various devices.

## System Configuration and Deployment Guide

This section outlines the procedures required to configure and deploy a personal instance of the RateCon Tracker application.

### 1. Prerequisites

A successful deployment requires the following accounts and resources:

* A GitHub account.
* A Google Cloud Platform (GCP) account with an active project.
* A Google Sheet to serve as the data backend.

### 2. Backend and API Configuration

1.  **Repository Forking:** Initiate the process by forking this repository to create a personal copy under your GitHub account.
2.  **Google Services Setup:**
    * Establish a new Google Sheet, ensuring the primary worksheet is titled "Sheet1".
    * Within your designated Google Cloud Platform project, activate both the **Google Drive API** and the **Google Sheets API**.
    * Generate a new Service Account and assign it the "Editor" role to permit programmatic data manipulation.
    * Proceed to create and download a JSON key file for this service account. The contents of this file are required for the secrets configuration during deployment.
    * Delegate "Editor" access to your Google Sheet for the service account by sharing the sheet with the `client_email` address specified within the downloaded JSON key.

### 3. Deployment to Streamlit Community Cloud

1.  **Initiate Deployment:** Begin the deployment process on the Streamlit Community Cloud platform.
2.  **Repository Selection:** Authenticate with your GitHub credentials and select the previously forked repository for deployment.
3.  **Secrets Configuration:** Navigate to the "Advanced settings" section of the deployment configuration. Here, you must provide the GCP service account credentials within the "Secrets" field. The credentials must be formatted using the TOML (Tom's Obvious, Minimal Language) syntax as demonstrated in the example below. **Important:** You must replace all placeholder values (e.g., `"your-gcp-project-id"`) with the actual credentials from your downloaded JSON key file.
    ```toml
    [gcp_service_account]
    type = "service_account"
    project_id = "your-gcp-project-id"
    private_key_id = "your-private-key-id"
    private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n"
    client_email = "your-service-account-email@your-project.iam.gserviceaccount.com"
    client_id = "your-client-id"
    auth_uri = "[https://accounts.google.com/o/oauth2/auth](https://accounts.google.com/o/oauth2/auth)"
    token_uri = "[https://oauth2.googleapis.com/token](https://oauth2.googleapis.com/token)"
    auth_provider_x509_cert_url = "[https://www.googleapis.com/oauth2/v1/certs](https://www.googleapis.com/oauth2/v1/certs)"
    client_x509_cert_url = "[https://www.googleapis.com/oauth2/v1/certs/](https://www.googleapis.com/oauth2/v1/certs/)..."
    ```
4.  **Finalize Deployment:** Finalize the configuration and commence the deployment. The application will be provisioned and made accessible at a public Uniform Resource Locator (URL) upon successful completion of this process.

## Accessing the Application

Once deployed, the application can be accessed at the following URL:

`https://your-app-name.streamlit.app`
