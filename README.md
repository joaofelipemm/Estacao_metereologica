# Estacao_metereologica

Le as linhas enviadas por uma porta serial e grava as leituras em CSV.

## Instalacao

```powershell
python -m pip install -r requirements.txt
```

## Uso

Quando nenhuma porta e informada, o programa detecta automaticamente a unica porta disponivel. A leitura usa 9600 baud e grava em:

`G:\Meu Drive\Estacao_prototype\leituras.csv`

Para testar a conexao lendo uma unica linha:

```powershell
python main.py --porta COM6 --once
```

Para manter a leitura ativa ate pressionar `Ctrl+C`:

```powershell
python main.py --porta COM6 --baudrate 9600
```

Tambem e possivel informar outro arquivo de saida com `--arquivo`.
