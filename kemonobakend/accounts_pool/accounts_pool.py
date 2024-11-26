
from http.cookies import SimpleCookie
from typing import Optional

from .accounts_register import AccountRegister

class Account:
    def __init__(self, username, password, cookies: Optional[SimpleCookie]=None, register: Optional[AccountRegister] = None):
        self.username = username
        self.password = password
        self.register = register
        self.cookies = cookies
    
    def set_cookies(self, cookies):
        self.cookies = cookies
    
    async def get_cookies(self, proxy = None):
        if self.cookies is None:
            if self.register is None:
                return None
            cookies = await self.register.login_account(self.username, self.password, proxy)
            if not cookies:
                return None
            self.cookies = cookies
        return self.cookies
    
    async def try_register(self, proxy = None):
        cookies = await self.register.register_account(self.username, self.password, proxy)
        if cookies:
            self.cookies = cookies
            return True
        return False
    
    async def __eq__(self, other):
        if not isinstance(other, Account):
            return False
        return self.username == other.username and self.password == other.password

class AccountsPool:
    def __init__(self, account_dicts = None, session_pool = None):
        self.session_pool = session_pool
        self.accounts_register = AccountRegister(session_pool)
        self.accounts = [Account(register=self.accounts_register, **acc) for acc in account_dicts] if account_dicts else self.get_default_accounts()

    def get_default_accounts(self):
        root = "prowizdther"
        nums = 100
        usernames = [f"{root}{hex(int("1" + str(i).zfill(2)))}" for i in range(nums)]
        return [Account(n, n, register=self.accounts_register) for n in usernames]
    
    def add_account(self, account):
        self.accounts.append(account)

    def remove_account(self, account):
        self.accounts.remove(account)
