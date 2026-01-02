# main.py
import os
import logging
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ConversationHandler
from dotenv import load_dotenv
from handlers import user_handlers, admin_handlers
from jobs import club_monitor, player_updater

load_dotenv()
logging.basicConfig(level=logging.INFO)

def main():
    app = Application.builder().token(os.getenv("BOT_TOKEN")).build()

    # User commands
    app.add_handler(CommandHandler("start", user_handlers.start))
    app.add_handler(CommandHandler("help", user_handlers.help_command))
    app.add_handler(CommandHandler("register", user_handlers.register))
    app.add_handler(CommandHandler("navigator", user_handlers.navigator))
    app.add_handler(CommandHandler("me", user_handlers.me))
    app.add_handler(CommandHandler("you", user_handlers.you))
    app.add_handler(CommandHandler("top", user_handlers.top))
    app.add_handler(CommandHandler("club", user_handlers.club))

    # Callbacks
    app.add_handler(CallbackQueryHandler(user_handlers.top_callback, pattern="^top_"))
    app.add_handler(CallbackQueryHandler(user_handlers.nav_callback, pattern="^nav_"))

    # Admin
    if os.getenv("ADMIN_USER_ID"):
        app.add_handler(CommandHandler("ACK", admin_handlers.ack))
        app.add_handler(CommandHandler("history", admin_handlers.history))
        app.add_handler(CommandHandler("we", admin_handlers.we))
        app.add_handler(CallbackQueryHandler(admin_handlers.ack_callback, pattern="^ack_"))
        app.add_handler(CallbackQueryHandler(admin_handlers.approve_reject_whois, pattern="^(approve_|reject_|whois_)"))
        app.add_handler(CallbackQueryHandler(admin_handlers.we_callback, pattern="^we_user_"))
        app.add_handler(CallbackQueryHandler(admin_handlers.we_action, pattern="^we_(norm_|del_)"))

    # Jobs
    app.job_queue.run_repeating(club_monitor.check_club_changes, interval=300)
    app.job_queue.run_repeating(player_updater.update_players_cache, interval=300)

    app.run_polling()

if __name__ == "__main__":
    main()