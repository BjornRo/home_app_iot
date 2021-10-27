from flask import Blueprint

auth = Blueprint('auth',__name__)

@auth.route('/login')
def login():
    return ""

@auth.route('/logout')
def logout():
    return ""

@auth.route('/sign-up')
def sign_up():
    return ""