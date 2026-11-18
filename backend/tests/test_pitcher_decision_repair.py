import gzip
from pathlib import Path

import duckdb

from scripts.repair_pitcher_decision_sources import repair_game


def test_targeted_repair_preserves_other_games_and_original_backup(tmp_path: Path):
    root=tmp_path/'data';year=2024;pk=77
    season=root/f'MLB{year}';season.mkdir(parents=True)
    output=root/'repair';(output/'sources').mkdir(parents=True)
    csv='game_pk,at_bat_number,pitch_number,game_type\n77,1,1,R\n88,1,1,R\n'
    (season/f'mlb_{year}_pitches.csv.gz').write_bytes(gzip.compress(csv.encode()))
    incoming='game_pk,at_bat_number,pitch_number,game_type\n'+''.join(f'77,{i},1,R\n' for i in range(1,102))
    (output/'sources'/f'statcast_{pk}.csv.gz').write_bytes(gzip.compress(incoming.encode()))
    db=season/f'mlb_{year}.duckdb'
    with duckdb.connect(str(db)) as c:
        c.execute("CREATE TABLE pitches AS SELECT 77::BIGINT game_pk,1::BIGINT at_bat_number,1::BIGINT pitch_number,'77_1_1' pitch_uid,'R' game_type UNION ALL SELECT 88,1,1,'88_1_1','R'")
        c.execute('CREATE TABLE games AS SELECT 77 game_pk,1 total_pitches,1 total_plate_appearances UNION ALL SELECT 88,1,1')
        c.execute("CREATE TABLE season_meta AS SELECT 'pitch_rows' AS key,'2' AS value")
    first=repair_game(year,pk,root,output)
    second=repair_game(year,pk,root,output)
    assert first['before_rows']==second['before_rows']==1
    assert first['after_rows']==second['after_rows']==101
    assert first['csv_roundtrip_exact'] and first['unrelated_games_unchanged']
    with duckdb.connect(str(db),read_only=True) as c:
        assert c.execute('SELECT pitch_uid FROM pitches WHERE game_pk=88').fetchall()==[('88_1_1',)]
        assert c.execute('SELECT total_pitches FROM games WHERE game_pk=77').fetchone()[0]==101
