# Environment Setup Guide

This document describes all environment variables that can be used to configure the Clinical Trials MCP Server.

## Required Environment Variables

### `ANTHROPIC_API_KEY`
- **Description**: Your Anthropic API key for Claude access
- **Required**: Yes
- **Example**: `sk-ant-api03-...`
- **Where to get**: [Anthropic Console](https://console.anthropic.com/)

## Optional Environment Variables

### API Endpoints

#### `CLINICALTRIALS_API_URL`
- **Description**: Base URL for the ClinicalTrials.gov API
- **Default**: `https://clinicaltrials.gov/api/v2/studies`
- **Example**: `https://clinicaltrials.gov/api/v2/studies`

#### `ANTHROPIC_API_URL`
- **Description**: Base URL for the Anthropic API
- **Default**: `https://api.anthropic.com/v1/messages`
- **Example**: `https://api.anthropic.com/v1/messages`

### Timeout Configuration

#### `CLINICALTRIALS_TIMEOUT`
- **Description**: Timeout for ClinicalTrials.gov API requests (seconds)
- **Default**: `10`
- **Example**: `15`

#### `ANTHROPIC_TIMEOUT`
- **Description**: Timeout for Anthropic API requests (seconds)
- **Default**: `30`
- **Example**: `45`

### Anthropic API Configuration

#### `ANTHROPIC_MODEL`
- **Description**: Claude model to use for text generation
- **Default**: `claude-3-opus-20240229`
- **Example**: `claude-3-sonnet-20240229`

#### `ANTHROPIC_MAX_TOKENS`
- **Description**: Maximum tokens for Claude responses
- **Default**: `1000`
- **Example**: `1500`

### Retry Configuration

#### `MAX_RETRIES`
- **Description**: Maximum number of retry attempts for failed requests
- **Default**: `3`
- **Example**: `5`

#### `RETRY_INITIAL_DELAY`
- **Description**: Initial delay between retries (seconds)
- **Default**: `1.0`
- **Example**: `2.0`

#### `RETRY_BACKOFF_FACTOR`
- **Description**: Factor to multiply delay by after each retry
- **Default**: `2.0`
- **Example**: `1.5`

#### `RETRY_MAX_DELAY`
- **Description**: Maximum delay between retries (seconds)
- **Default**: `60.0`
- **Example**: `120.0`

#### `RETRY_JITTER`
- **Description**: Whether to add random jitter to retry delays
- **Default**: `true`
- **Example**: `false`
- **Values**: `true`, `false`, `1`, `0`, `yes`, `no`, `on`, `off`

### Cache Configuration

#### `CACHE_SIZE`
- **Description**: Maximum number of cached query results
- **Default**: `100`
- **Example**: `200`

#### `CACHE_TTL`
- **Description**: Cache time-to-live (seconds)
- **Default**: `3600` (1 hour)
- **Example**: `7200` (2 hours)

### Circuit Breaker Configuration (Future Use)

#### `CIRCUIT_BREAKER_FAILURE_THRESHOLD`
- **Description**: Number of failures before circuit breaker opens
- **Default**: `5`
- **Example**: `10`

#### `CIRCUIT_BREAKER_RECOVERY_TIMEOUT`
- **Description**: Time before attempting to close circuit breaker (seconds)
- **Default**: `60`
- **Example**: `120`

### User Agent Configuration

#### `USER_AGENT`
- **Description**: User-Agent header for API requests
- **Default**: `mutation-clinical-trial-matching-mcp/0.1.0 (Clinical Trials MCP Server)`
- **Example**: `my-custom-app/1.0.0`

## Environment File Setup

### 1. Create `.env` file

Copy the example below to create your `.env` file:

```bash
# Required
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Optional - only include if you want to override defaults
# CLINICALTRIALS_TIMEOUT=15
# ANTHROPIC_TIMEOUT=45
# MAX_RETRIES=5
# CACHE_SIZE=200
```

### 2. Example `.env` file

```bash
# API Configuration
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Timeout Settings (optional)
CLINICALTRIALS_TIMEOUT=15
ANTHROPIC_TIMEOUT=45

# Retry Configuration (optional)
MAX_RETRIES=5
RETRY_INITIAL_DELAY=2.0
RETRY_BACKOFF_FACTOR=1.5

# Cache Configuration (optional)
CACHE_SIZE=200
CACHE_TTL=7200

# User Agent (optional)
USER_AGENT=my-clinical-trials-app/1.0.0
```

## Configuration Validation

The server validates all configuration on startup and will fail with clear error messages if:

- Required variables are missing
- URLs are malformed
- Numeric values are invalid or out of range
- Logical constraints are violated (e.g., initial delay > max delay)

## Development vs Production

### Development
- Use smaller timeout values for faster feedback
- Enable verbose logging
- Use smaller cache sizes to test cache behavior

### Production
- Use longer timeout values for stability
- Optimize cache size based on usage patterns
- Consider circuit breaker thresholds based on traffic

## Security Considerations

- Never commit `.env` files to version control
- Use environment-specific configuration management in production
- Rotate API keys regularly
- Monitor API usage and set appropriate rate limits

## Troubleshooting

### Common Issues

1. **Missing API Key**: 
   - Error: `ANTHROPIC_API_KEY is required`
   - Solution: Add your API key to the `.env` file

2. **Invalid URLs**:
   - Error: `CLINICALTRIALS_API_URL must be a valid URL`
   - Solution: Ensure URLs start with `http://` or `https://`

3. **Invalid Numeric Values**:
   - Error: `CLINICALTRIALS_TIMEOUT must be positive`
   - Solution: Use positive numbers for timeout values

4. **Logical Constraints**:
   - Error: `RETRY_INITIAL_DELAY cannot be greater than RETRY_MAX_DELAY`
   - Solution: Ensure initial delay ≤ max delay

### Configuration Testing

To test your configuration:

```bash
# Run with configuration validation
uv run python -c "from clinicaltrials.config import get_config; print('Configuration valid!')"
```

## Environment Variables Reference

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | string | Yes | - | Anthropic API key |
| `CLINICALTRIALS_API_URL` | string | No | `https://clinicaltrials.gov/api/v2/studies` | ClinicalTrials.gov API endpoint |
| `ANTHROPIC_API_URL` | string | No | `https://api.anthropic.com/v1/messages` | Anthropic API endpoint |
| `CLINICALTRIALS_TIMEOUT` | int | No | `10` | ClinicalTrials.gov timeout (seconds) |
| `ANTHROPIC_TIMEOUT` | int | No | `30` | Anthropic API timeout (seconds) |
| `ANTHROPIC_MODEL` | string | No | `claude-3-opus-20240229` | Claude model to use |
| `ANTHROPIC_MAX_TOKENS` | int | No | `1000` | Maximum tokens for responses |
| `MAX_RETRIES` | int | No | `3` | Maximum retry attempts |
| `RETRY_INITIAL_DELAY` | float | No | `1.0` | Initial retry delay (seconds) |
| `RETRY_BACKOFF_FACTOR` | float | No | `2.0` | Retry backoff multiplier |
| `RETRY_MAX_DELAY` | float | No | `60.0` | Maximum retry delay (seconds) |
| `RETRY_JITTER` | bool | No | `true` | Enable retry jitter |
| `CACHE_SIZE` | int | No | `100` | Maximum cache entries |
| `CACHE_TTL` | int | No | `3600` | Cache time-to-live (seconds) |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | int | No | `5` | Circuit breaker failure threshold |
| `CIRCUIT_BREAKER_RECOVERY_TIMEOUT` | int | No | `60` | Circuit breaker recovery timeout (seconds) |
| `USER_AGENT` | string | No | `mutation-clinical-trial-matching-mcp/0.1.0 (Clinical Trials MCP Server)` | User-Agent header |