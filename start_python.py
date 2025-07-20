# start.py - Script Python pour démarrage Railway
import os
import uvicorn

def main():
    # Récupère le port depuis Railway
    port = int(os.getenv("PORT", 8000))
    
    print(f"🚀 Starting FastAPI on port {port}")
    print(f"📊 Railway Environment: {os.getenv('RAILWAY_ENVIRONMENT', 'false')}")
    print(f"🔗 PORT variable: {os.getenv('PORT', 'not set')}")
    
    # Liste toutes les variables Railway
    railway_vars = {k: v for k, v in os.environ.items() if k.startswith("RAILWAY_")}
    if railway_vars:
        print("🔗 Railway variables:")
        for k, v in railway_vars.items():
            print(f"  {k}: {v}")
    else:
        print("⚠️ No Railway variables found")
    
    # Importe et démarre l'app
    try:
        from main import app
        print("✅ App imported successfully")
        
        # Démarre uvicorn
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info",
            access_log=True
        )
    except Exception as e:
        print(f"❌ Error starting app: {e}")
        raise

if __name__ == "__main__":
    main()