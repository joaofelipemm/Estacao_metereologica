# Estacao_metereologica

Le as linhas enviadas por uma porta serial, grava as leituras em CSV localmente e sincroniza os novos registros com o Supabase.

## Organizacao

- `serial_reader.py`: encontra a porta e le as mensagens do sensor.
- `csv_storage.py`: interpreta as mensagens e grava ou le o CSV.
- `database_sync.py`: envia somente registros posteriores ao checkpoint.
- `main.py`: coordena a leitura, o CSV e a sincronizacao.
- `upload_file.py`: sincroniza manualmente um CSV existente.

O arquivo `ultima_sincronizacao.json` guarda a ultima data e hora confirmada no
Supabase. Ele so e atualizado depois que todos os lotes forem enviados com sucesso.

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
    chuva_acumulada NUMERIC(10,3) NOT NULL,
    taxa_chuva NUMERIC(10,3) NOT NULL,
    temperatura NUMERIC(5,2) NOT NULL,
    umidade NUMERIC(5,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_leituras_data_hora
ON leituras (data, hora);
```

Se a tabela ja foi criada sem as colunas de chuva, atualize-a antes de executar
o sincronizador:

```sql
ALTER TABLE leituras
    ADD COLUMN IF NOT EXISTS chuva_acumulada NUMERIC(10,3) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS taxa_chuva NUMERIC(10,3) NOT NULL DEFAULT 0;

ALTER TABLE leituras
    ALTER COLUMN chuva_acumulada DROP DEFAULT,
    ALTER COLUMN taxa_chuva DROP DEFAULT;
```

No ambiente, configure uma das variaveis abaixo:

```powershell
$env:SUPABASE_DB_URL = "postgresql://postgres:senha@db.seu-projeto.supabase.co:5432/postgres"
# ou
$env:DATABASE_URL = "postgresql://postgres:senha@db.seu-projeto.supabase.co:5432/postgres"
```

Se a variavel nao estiver definida, o programa continua funcionando e grava apenas no CSV local.

Para enviar um CSV existente ao Supabase via API REST, configure `SUPABASE_URL` e
`SUPABASE_KEY` no arquivo `.env` e execute:

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

Para testar a leitura sem acessar o banco:

```powershell
python main.py --porta COM6 --once --sem-banco
```

Para manter a leitura ativa ate pressionar `Ctrl+C`:

```powershell
python main.py --porta COM6 --baudrate 9600
```

Tambem e possivel informar outro arquivo de saida com `--arquivo`.
