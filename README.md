# Amazon Order Trends

This project is a full-stack web application designed to help you track and analyze your Amazon order history. It provides a dashboard to visualize your spending trends, a searchable and sortable table of all your orders, and insights into your most frequently reordered items.

## Features

- **Interactive Dashboard**: Get a quick overview of your total spending and number of orders. Visualize your monthly spending trends with an interactive chart.
- **Detailed Order History**: View all your Amazon orders in a comprehensive table. Search, sort, and filter your orders to easily find what you're looking for.
- **Repeat Order Insights**: Identify items you buy frequently and see how often you reorder them.
- **Price Tracking**: Track price changes and configure notifications for price changes per item.
- **Secure Authentication**: The application uses a secure authentication system to protect your data.
- **User Management (Admin)**: Admins can manage users and their roles.

## Getting Started (Production)

These instructions will get you a copy of the project up and running in a production environment using Docker.

### Prerequisites

- [Docker](https://www.docker.com/get-started)

### Installation & Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/your-username/amazon-order-trends.git
   cd amazon-order-trends
   ```

2. **Build the Docker image:**

   ```bash
   docker build -t amazon-order-trends .
   ```

3. **Run the Docker container:**

   You will need a running PostgreSQL instance. You can start one using Docker:

   ```bash
   docker run --name postgres-db -e POSTGRES_USER=your_db_user -e POSTGRES_PASSWORD=your_db_password -e POSTGRES_DB=amazon_orders -p 5432:5432 -d postgres
   ```

   Then, run the application container, linking it to the database. Make sure to provide the necessary environment variables.

   ```bash
   docker run --name amazon-order-trends-app \
     -p 5001:5001 \
     -e POSTGRES_HOST=<your_postgres_host> \
     -e POSTGRES_USER=your_db_user \
     -e POSTGRES_PASSWORD=your_db_password \
     -e POSTGRES_DB=amazon_orders \
     -e POSTGRES_PORT=5432 \
     -e ADMIN_USERNAME=admin \
     -e ADMIN_PASSWORD=your_admin_password \
     -e ENCRYPTION_KEY=$(openssl rand -hex 32) \
     -d amazon-order-trends
   ```

   Replace `<your_postgres_host>` with the IP address of your PostgreSQL container or server. If running the database container on the same Docker network, you can link them.

## Usage

- **Access the application**: Open your web browser and navigate to `http://localhost:5001`.
- **Login**: Use the admin credentials you configured in the environment variables to log in.
- **Ingest Data**: To populate the database with your Amazon order data, you will need to run the ingestion script. The details of this process will be added here.

## Development

For development, you can use `docker-compose` to run the application with hot-reloading for both the frontend and backend.

1. **Create an environment file:**

   Create a `.env` file in the root of the project. See the `docker-compose.yml` file for the required variables.

2. **Run the application:**

   ```bash
   docker-compose up --build
   ```

   The frontend will be available at `http://localhost:3000` and the backend at `http://localhost:5001`.

## Acknowledgements

This project utilizes the `amazon-orders` Python package to work with Amazon order data. A big thank you to the creator and maintainers of this package.

- [amazon-orders on PyPI](https://pypi.org/project/amazon-orders/)
- [amazon-orders on GitHub](https://github.com/hax FR/amazon-orders)

## Project Structure

- `api/`: Contains the Flask backend application.
- `frontend/`: Contains the React frontend application.
- `ingestion/`: Contains scripts for ingesting Amazon order data.
- `shared/`: Contains shared modules used by both the backend and ingestion scripts.
