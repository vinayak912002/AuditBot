import argparse
from src.common.db import init_db

def main():
    parser = argparse.ArgumentParser(description="AuditBot Management")
    parser.add_argument("--init-db", action="store_true", help="Initialize the database tables")
    
    args = parser.parse_args()
    
    if args.init_db:
        print("Initializing database...")
        init_db()
        print("Database initialized.")
    else:
        print("AuditBot Service. Use --init-db to initialize or run services via Docker.")

if __name__ == "__main__":
    main()
