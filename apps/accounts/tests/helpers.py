from apps.accounts.models import User

PASSWORD = "correct-horse-battery-staple"


def make_user(username: str = "learner", email: str = "", password: str = PASSWORD) -> User:
    email = email or f"{username}@example.com"
    return User.objects.create_user(username=username, email=email, password=password)
