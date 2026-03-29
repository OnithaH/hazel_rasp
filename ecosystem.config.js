module.exports = {
  apps: [
    {
      name: "hazel-master",
      script: "/home/hazel123/Documents/hazel_rasp/main_controller/main_controller.py",
      interpreter: "/home/hazel123/Documents/hazel_rasp/main_controller/venv/bin/python3",
      autorestart: true
    },
    {
      name: "hazel-db-sync",
      script: "/home/hazel123/Documents/hazel_rasp/hazel_services/db_sync_worker.py",
      interpreter: "/home/hazel123/Documents/hazel_rasp/hazel_services/venv/bin/python3",
      autorestart: true
    }
  ]
}