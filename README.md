# Estacao_metereologica

Le as linhas enviadas por uma porta serial e grava as leituras em CSV localmente, além de persistir no PostgreSQL/Supabase.

## Instalacao

```powershell
python -m pip install -r requirements.txt
```

## Banco de dados PostgreSQL / Supabase

Crie uma tabela no seu banco com o seguinte SQL:

```sql
CREATE TABLE IF NOT EXISTS leituras (
    id SERIAL PRIMARY KEY,
    data DATE NOT NULL,
    hora TIME NOT NULL,
    temperatura NUMERIC(5,2) NOT NULL,
    umidade NUMERIC(5,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leituras_data_hora
ON leituras (data, hora);
```

No ambiente, configure uma das variaveis abaixo:

```powershell
$env:SUPABASE_DB_URL = "postgresql://postgres:senha@db.seu-projeto.supabase.co:5432/postgres"
# ou
$env:DATABASE_URL = "postgresql://postgres:senha@db.seu-projeto.supabase.co:5432/postgres"
```

Se a variavel nao estiver definida, o programa continua funcionando e grava apenas no CSV local.

Para enviar um CSV existente ao Supabase via API REST, configure `SUPABASE_URL` e
`SUPABASE_SERVICE_ROLE_KEY` no arquivo `.env` e execute:

```powershell
python upload_file.py caminho\para\leituras.csv
```

O script aceita os formatos de data `dd/mm/AAAA` e `AAAA-MM-DD` e envia os registros
em lotes de 100. Para alterar o tamanho do lote, use `--lote`, por exemplo:

```powershell
python upload_file.py caminho\para\leituras.csv --lote 500
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
