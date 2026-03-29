module.exports = {
  apps: [
    {
      name: "hazel-master",
      script: "/home/hazel123/Documents/hazel_rasp/main_controller/main_controller.py",
      interpreter: "/home/hazel123/Documents/hazel_rasp/main_controller/venv/bin/python3",
      autorestart: true
    },
    {
      name: "hazel-live-convo",
      script: "/home/hazel123/Documents/hazel_rasp/live_convo/live_convo.py",
      // Use the NEW venv inside the live_convo folder
      interpreter: "/home/hazel123/Documents/hazel_rasp/live_convo/venv/bin/python3",
      autorestart: false // Managed by main_controller
    }
  ]
}