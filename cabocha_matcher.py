from functools import reduce
from itertools import product
from cabocha_parser import CaboChaParser, Sentence, Chunk, Token


class CaboChaMatcher():
    def __init__(self):
        self.parser = CaboChaParser()

    def parse(self, sentence):
        '''
        CaboChaParserのparseを呼び出す．

        Args:
            sentence: str
                文
        Returns:
            Sentence
        '''
        return self.parser.parse(sentence)

    def parse_pat(self, pattern):
        '''
        CaboChaParserのto_senを呼び出す．

        Args:
            pattern: str
                パターン（CaboChaの出力に合わせる）
        Returns:
            Sentence
        '''
        return self.parser.to_sen(pattern)

    def match(self, sentence, pattern):
        '''
        センテンスとパターンのマッチングを行う．

        Args:
            sentence: Sentence
                マッチング対象になる文
            pattern: Sentence
                マッチングのパターン
        Returns:
            list(list(str))
                [['hoge', ...], [...], ...]を返す．
        '''
        matchedtoks = self.match_tok(sentence, pattern)
        res = self._tolist(matchedtoks)
        # res = self._tolist(self._tostr(matchedtoks))
        return res

    def _tolist(self, matchedtoks):
        '''
        マッチング結果をlist型に変換する．

        Args:
            matchedtoks: list[dict[int, T]]
                T = list[Token] or str
                マッチングの結果抽出されたトークン
        Returns:
            matchedtoks: list[list[T]]
        '''
        res = []

        if matchedtoks is None:
            return None

        for dic in matchedtoks:
            l = [tok for tid, tok in sorted(dic.items())]
            res.append(l)

        return res

    def _tostr(self, matchedtoks):
        '''
        マッチング結果をstr型に変換する．

        Args:
            matchedtoks: list[dict[int, list[Token]]]:
                マッチングの結果抽出されたトークン
        Returns:
            list[dict[int, str]]
                [{wild_tid: 'hoge', ...}, {...}, ...]を返す．
        '''
        res = []

        if matchedtoks is None:
            return None

        for dic in matchedtoks:
            d = {}
            for k, v in dic.items():
                # 持つ, 運ぶ => 持ち運ぶ
                part = ''.join(t.surface for t in v[:-1]) + \
                       v[-1].dictform
                d[k] = part
            res.append(d)
        return res

    def match_tok(self, sentence, pattern):
        '''
        センテンスとパターンのマッチングを行う．

        Args:
            sentence: Sentence
                マッチング対象になる文
            pattern: Sentence
                マッチングのパターン
        Returns:
            list[dict[int, list[Token]]]
                [{wild_tid: [Token, ...], ...}, {...}, ...]を返す．
        '''
        # チャンクごとにマッチングを行って，
        # 正しく係り受け関係を満たしているものを結果として返す

        # マッチング結果を格納するやつ
        # Type: dict[int, dict[int, dict[int, list[Token]]]]
        # {pcnk.cid: {scnk.cid: {ptok.tid: [Token, ...]}, ...}, ...}
        matching_res = {}

        # チャンクごとのマッチング
        for p_cnk in pattern.cnks:
            res = {}

            for s_cnk in sentence.cnks:
                # チャンク同士のマッチング
                r = self._match_chunk(s_cnk, p_cnk)

                # マッチなしなら次のセンテンスチャンクを見る
                if r is None:
                    continue

                # 抽出したトークンを記憶
                res[s_cnk.cid] = r


            # マッチするセンテンスチャンクがあったら次へ
            # なかったらマッチング終了
            if res:
                matching_res[p_cnk.cid] = res
                continue
            else:
                return None

        # 係り受け関係のチェック
        valid_edges = {}
        for p_cid in matching_res:
            # p_cidのパターンチャンクの掛かり先
            p_link = pattern.get_cnk(p_cid).link

            # 終端チャンクなら飛ばす
            if p_link == -1:
                continue

            # 掛かり先にマッチしたセンテンスチャンクのcid
            s_cids_p_link = set(matching_res[p_link].keys())

            # p_cidのパターンチャンクにマッチしたセンテンスチャンクのcid
            s_cids = set(matching_res[p_cid].keys())

            p_edge = (p_cid, p_link)
            s_edges = []

            # s_cid -> s_link が p_cid -> p_link に対応するかどうか
            for s_cid in s_cids:
                s_link = sentence.get_cnk(s_cid).link
                if s_link in s_cids_p_link:
                    s_edges.append((s_cid, s_link))

            # パターンの枝にマッチするセンテンスの道があったら記憶
            # なければマッチング失敗
            if s_edges:
                valid_edges[p_edge] = s_edges
                continue
            else:
                return None

        # 最終結果を格納するリスト
        res = []

        if valid_edges:
            # 制約を満たすエッジがある <=> パターンが単一チャンクではない場合，
            # 係り受け関係制約を満たすもののみ答えとする

            p_edges, list_s_edges = zip(*valid_edges.items())
            prd_s_edges = product(*list_s_edges)

            # 枝を構成するチャンクのcid（重複あり）
            p_cids = reduce(lambda x, y: list(x) + list(y),
                            p_edges, [])
            p_taioh = tuple(self._same_node(p_edges))

            for s_edges in prd_s_edges:
                s_taioh = tuple(self._same_node(s_edges))

                # 係り受け関係が正しそうなら
                if p_taioh == s_taioh:
                    # 枝を構成するチャンクのcid（重複あり）
                    s_cids = reduce(lambda x, y: list(x) + list(y),
                                    s_edges, [])

                    # その枝を構成するチャンクにマッチしたトークンを答えに追加
                    toks = {}
                    for p_cid, s_cid in zip(p_cids, s_cids):
                        toks.update(matching_res[p_cid][s_cid])
                    res.append(toks)
        else:
            # パターンが単一チャンクの場合，ここを通る
            # 係り受け関係とかどうでもいいから，マッチしたもの全部が答え
            for dic in matching_res.values():
                for toks in dic.values():
                    res.append(toks)

        return res

    def _same_node(self, edges):
        return map(lambda x: (x[0][0] == x[1][0], x[0][1] == x[1][1]),
                   product(edges, repeat=2))

    def _match_chunk(self, scnk, pcnk):
        '''
        チャンク単位でのマッチング．
        連語にもマッチする．
        o: "青春ラブコメは" "[*/名詞]は" => [<青春>, <ラブ>, <コメ>]
        x: "青春ラブコメは" "[*/名詞]は" => [<コメ>]

        Args:
            scnk: Chunk
                文のチャンク
            pcnk: Chunk
                パターンのチャンク
        Returns:
            dict[int, list[Token]] or None
                match => dict(ワイルドトークンのtid: マッチした語)
                not match => None
        '''
        SLENGTH = len(scnk.toks)
        PLENGTH = len(pcnk.toks)

        # この関数を再帰させる
        def match_token(si, pi, mode):
            '''
            センテンスチャンクとパターンチャンクの頭から
            トークンを1つずつ見ていって，マッチするパターンがあるか調べる．
            マッチしたらその辞書を，マッチしなかったらNoneを返す
            '''
            INITIAL, RECORDING, NORMAL = 0, 1, 2

            # 終了条件：無事に最後まで見終わったら空の辞書を返す
            if pi >= PLENGTH:
                if mode == INITIAL:
                    return {}
                elif mode == RECORDING:
                    return {}
                elif mode == NORMAL:
                    return None
            if si >= SLENGTH:
                return None

            stok = scnk.toks[si]
            ptok = pcnk.toks[pi]

            if ptok.is_slot and stok == ptok:
                # 普通のトークンとワイルドトークンの比較でマッチした場合
                # ひとまずセンテンスポインタだけ進めてみる
                res = match_token(si + 1, pi, RECORDING)
                if res is not None:
                    # マッチしたら結果に今読んだ文字を書き加える
                    res[ptok.tid] = [stok] + res.setdefault(ptok.tid, [])
                    return res

                # センテンスポインタだけ進めてダメだったら両方進めてみる
                res = match_token(si + 1, pi + 1, RECORDING)
                if res is not None:
                    # マッチしたら結果に今読んだ文字を書き加える
                    res[ptok.tid] = [stok] + res.setdefault(ptok.tid, [])
                    return res

                # それでもダメならマッチング失敗 => Noneを返す
                return None

            elif ptok.is_slot and stok != ptok:
                # 普通のトークンとワイルドトークンの比較でマッチしなかった場合
                # パターンポインタを進める
                if mode == INITIAL:
                    return None
                elif mode == RECORDING:
                    return match_token(si, pi + 1, NORMAL)
                elif mode == NORMAL:
                    return None

            elif not ptok.is_slot and stok == ptok:
                # 普通のトークン同士の比較でマッチした場合
                # ともにポインタを進めて読み飛ばす
                return match_token(si + 1, pi + 1, mode)

            elif not ptok.is_slot and stok != ptok:
                # 普通のトークン同士の比較でマッチしなかった場合
                # マッチング失敗 => Noneを返す
                return None

        matching_res = match_token(0, 0, 0)
        return matching_res
