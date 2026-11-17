@echo off
chcp 65001 >nul
title Cupons em Lote - VTEX
cd /d "%~dp0"

set PY=python
where python >nul 2>nul || set PY=py
%PY% --version >nul 2>nul || (
  echo.
  echo  Python nao encontrado. Instale em https://www.python.org/downloads/
  echo  e marque "Add Python to PATH" na instalacao.
  echo.
  pause
  exit /b
)

echo.
echo  Preparando o app (so demora na primeira vez)...
%PY% -m pip install -q --disable-pip-version-check -r requirements.txt

echo.
echo  ============================================
echo   Cupons em Lote aberto no navegador.
echo   Deixe esta janela aberta enquanto usa.
echo   Para encerrar, feche esta janela.
echo  ============================================
%PY% app.py
pause
