git rm --cached .env
echo ".env" >> .gitignore
git add .gitignore
git commit -m "Remove .env from repo"
git push