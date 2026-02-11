from flask import Blueprint, jsonify, current_app
import requests
from flask_jwt_extended import jwt_required

releases_bp = Blueprint('releases_bp', __name__)

@releases_bp.route('/api/releases', methods=['GET'])
@jwt_required()
def get_releases():
    """
    Fetches the list of releases from the GitHub repository.
    """
    repo_owner = "bodybuildingfly"
    repo_name = "amazon-order-trends"
    url = f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases"

    try:
        # GitHub API has a rate limit for unauthenticated requests, but it should be sufficient for this use case.
        # If necessary, we can add a GITHUB_TOKEN environment variable.
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        releases = response.json()
        return jsonify(releases)
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Failed to fetch releases from GitHub: {e}")
        return jsonify({"error": "Failed to fetch releases"}), 500
