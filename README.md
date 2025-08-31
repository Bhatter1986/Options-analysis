# README.md
# Dhan Options Analysis API

A FastAPI application that integrates Dhan's trading API with OpenAI for options analysis.

## Features

- Dhan API integration for market data, orders, and portfolio
- OpenAI-powered options analysis and strategy recommendations
- Instrument database with CSV fallback
- Secure webhook verification
- CORS enabled for frontend integration

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your credentials
4. Run the application: `uvicorn main:app --reload`

## Environment Variables

- `MODE`: SANDBOX or LIVE
- `WEBHOOK_SECRET`: Secret for webhook verification
- `DHAN_CLIENT_ID`: Your Dhan client ID
- `DHAN_ACCESS_TOKEN`: Your Dhan access token
- `OPENAI_API_KEY`: Your OpenAI API key

## API Endpoints

See the interactive documentation at `/docs` when the server is running.
q
## Deployment

The application can be deployed to Render using the provided `render.yaml` file.
