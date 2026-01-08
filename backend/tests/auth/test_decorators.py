"""
Tests for authorization decorators.

Tests admin-only route protection.
"""

import pytest
from flask import Flask, request, jsonify
from auth.decorators import require_admin


class MockUser:
    """Mock user object for testing."""
    def __init__(self, user_id, is_admin):
        self.id = user_id
        self.is_admin = is_admin
        self['id'] = user_id
        self['is_admin'] = is_admin

    def __getitem__(self, key):
        return getattr(self, key)


class TestRequireAdminDecorator:
    """Test @require_admin decorator."""

    @pytest.fixture
    def app(self):
        """Create Flask app for testing."""
        app = Flask(__name__)
        app.config['TESTING'] = True
        return app

    def test_allows_admin_user(self, app):
        """Test admin user can access protected route."""
        @app.route('/test')
        @require_admin(lambda: None)
        def test_route():
            return jsonify({"message": "success"})

        with app.test_request_context('/test'):
            # Set admin user
            request.current_user = {'id': 1, 'is_admin': True}

            response = test_route()
            assert response.json['message'] == 'success'

    def test_blocks_non_admin_user(self, app):
        """Test non-admin user cannot access protected route."""
        @app.route('/test')
        @require_admin(lambda: None)
        def test_route():
            return jsonify({"message": "success"})

        with app.test_request_context('/test'):
            # Set non-admin user
            request.current_user = {'id': 2, 'is_admin': False}

            response, status_code = test_route()
            assert status_code == 403
            assert 'Admin access required' in response.json['error']

    def test_blocks_unauthenticated_request(self, app):
        """Test unauthenticated request is blocked."""
        @app.route('/test')
        @require_admin(lambda: None)
        def test_route():
            return jsonify({"message": "success"})

        with app.test_request_context('/test'):
            # No current_user set
            response, status_code = test_route()
            assert status_code == 401
            assert 'Authentication required' in response.json['error']

    def test_blocks_when_current_user_is_none(self, app):
        """Test None current_user is blocked."""
        @app.route('/test')
        @require_admin(lambda: None)
        def test_route():
            return jsonify({"message": "success"})

        with app.test_request_context('/test'):
            # Set current_user to None
            request.current_user = None

            response, status_code = test_route()
            assert status_code == 401

    def test_preserves_request_current_user(self, app):
        """Test decorator preserves request.current_user for route."""
        @app.route('/test')
        @require_admin(lambda: None)
        def test_route():
            # Verify current_user is still available in the route
            return jsonify({"user_id": request.current_user['id']})

        with app.test_request_context('/test'):
            request.current_user = {'id': 1, 'is_admin': True}

            response = test_route()
            assert response.json['user_id'] == 1
