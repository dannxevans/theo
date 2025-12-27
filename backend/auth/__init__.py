# Auth package for THEO Personal AI Agent

# Import auth functions from the parent module (auth.py file)
import sys
import os

# Add parent directory to path to import auth.py
parent_dir = os.path.dirname(os.path.dirname(__file__))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Now we can import from the auth.py file by using a different name
import importlib.util
spec = importlib.util.spec_from_file_location("auth_module", os.path.join(parent_dir, "auth.py"))
auth_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auth_module)

# Re-export functions from auth.py
init_default_user = auth_module.init_default_user
hash_password = auth_module.hash_password
verify_password = auth_module.verify_password
generate_session_token = auth_module.generate_session_token
