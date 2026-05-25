import numpy as np

class RankBasedLinkageClustering:
    """
    Python implementation of the NSA's Rank-Based Linkage (RBL) clustering algorithm.
    As described in:
    "Rank-based linkage I: triplet comparisons and oriented simplicial complexes"
    by R.W.R. Darling, Will Grilliette, and Adam Logan (2025/2023).
    """
    def __init__(self, k=8, max_cluster=None, in_sway_threshold=None, higher_weight_more_similar=False):
        self.k = k
        self.max_cluster = max_cluster
        self.in_sway_threshold = in_sway_threshold
        self.higher_weight_more_similar = higher_weight_more_similar

    def fit_predict(self, D):
        """
        Fits RBL on a distance (or similarity) matrix D and returns cluster labels.
        D is a 2D numpy array of shape (N, N).
        If higher_weight_more_similar is False, D is treated as a distance matrix (lower is better).
        If higher_weight_more_similar is True, D is treated as a similarity matrix (higher is better).
        """
        N = D.shape[0]
        
        # 1. 2-core extraction
        # Active edges are those that are not np.inf or np.nan and not self-loops
        valid_mask = ~np.isinf(D) & ~np.isnan(D)
        np.fill_diagonal(valid_mask, False)
        
        # Build adjacency list for 2-core calculation (undirected representation)
        adj_undir = {i: set() for i in range(N)}
        edges = []
        edge_map = {} # maps (u, v) -> edge_idx
        
        for u in range(N):
            for v in np.where(valid_mask[u])[0]:
                e_idx = len(edges)
                edges.append((u, v, D[u, v]))
                edge_map[(u, v)] = e_idx
                adj_undir[u].add((v, e_idx))
                adj_undir[v].add((u, e_idx))
                
        deg = np.array([len(adj_undir[i]) for i in range(N)])
        vertex_active = np.ones(N, dtype=bool)
        edge_active = np.ones(len(edges), dtype=bool)
        
        queue = [v for v in range(N) if deg[v] < 2]
        in_queue = set(queue)
        
        while queue:
            u = queue.pop(0)
            vertex_active[u] = False
            for v, e_idx in list(adj_undir[u]):
                if edge_active[e_idx]:
                    edge_active[e_idx] = False
                    deg[v] -= 1
                    if deg[v] < 2 and v not in in_queue:
                        queue.append(v)
                        in_queue.add(v)
                        
        core_nodes = np.where(vertex_active)[0]
        if len(core_nodes) == 0:
            return np.full(N, -1)
            
        # 2. Build K-NN digraph on the 2-core nodes
        # For each core vertex u, find the K nearest neighbors among other core vertices.
        gamma = {u: [] for u in core_nodes}
        gamma_sets = {u: set() for u in core_nodes}
        
        for u in core_nodes:
            candidates = []
            for v in core_nodes:
                if u == v:
                    continue
                if (u, v) in edge_map and edge_active[edge_map[(u, v)]]:
                    candidates.append((v, D[u, v]))
            
            # Sort candidates by distance (or similarity)
            if self.higher_weight_more_similar:
                candidates.sort(key=lambda x: x[1], reverse=True)
            else:
                candidates.sort(key=lambda x: x[1])
                
            top_k = [v for v, w in candidates[:self.k]]
            gamma[u] = top_k
            gamma_sets[u] = set(top_k)
            
        # 3. Find mutual friends L (unordered pairs)
        mutual_friends = []
        for u in core_nodes:
            for v in gamma[u]:
                if u < v and u in gamma_sets[v]:
                    mutual_friends.append((u, v))
                    
        # 4. Compute in-sway for each mutual friend pair {x, z}
        # Precompute incoming edges for each node in KNN digraph
        incoming = {u: set() for u in core_nodes}
        for u in core_nodes:
            for v in gamma[u]:
                incoming[v].add(u)
                
        def xz_is_source(x, z, y):
            def prefers(a, b, c):
                w_ab = D[a, b]
                w_ac = D[a, c]
                if self.higher_weight_more_similar:
                    return w_ab > w_ac
                else:
                    return w_ab < w_ac
                    
            xz_beats_xy = (y not in gamma_sets[x]) or prefers(x, z, y)
            xz_beats_yz = (y not in gamma_sets[z]) or prefers(z, x, y)
            return xz_beats_xy and xz_beats_yz

        insway_scores = {}
        for x, z in mutual_friends:
            y_candidates = incoming[x].union(incoming[z])
            y_candidates.discard(x)
            y_candidates.discard(z)
            
            count = 0
            for y in y_candidates:
                if xz_is_source(x, z, y):
                    count += 1
            insway_scores[(x, z)] = count
            
        if len(mutual_friends) == 0:
            return np.full(N, -1)
            
        # 5. Determine the threshold t
        max_insway = max(insway_scores.values()) if insway_scores else 0
        
        links_by_insway = {val: [] for val in range(max_insway + 1)}
        for edge, val in insway_scores.items():
            links_by_insway[val].append(edge)
            
        class UnionFind:
            def __init__(self, elements):
                self.parent = {el: el for el in elements}
                self.size = {el: 1 for el in elements}
            def find(self, i):
                path = []
                while self.parent[i] != i:
                    path.append(i)
                    i = self.parent[i]
                for node in path:
                    self.parent[node] = i
                return i
            def union(self, i, j):
                root_i = self.find(i)
                root_j = self.find(j)
                if root_i != root_j:
                    if self.size[root_i] < self.size[root_j]:
                        root_i, root_j = root_j, root_i
                    self.parent[root_j] = root_i
                    self.size[root_i] += self.size[root_j]
            def get_max_component_size(self):
                roots = [self.find(el) for el in self.parent]
                if not roots:
                    return 0
                root_sizes = {}
                for r in roots:
                    root_sizes[r] = root_sizes.get(r, 0) + 1
                return max(root_sizes.values()) if root_sizes else 0
                
        if self.in_sway_threshold is not None:
            t = self.in_sway_threshold
        elif self.max_cluster is not None:
            uf = UnionFind(core_nodes)
            max_size = 1
            curr_val = max_insway + 1
            max_size_by_val = {curr_val: max_size}
            
            while max_size < self.max_cluster + 1 and curr_val > 0:
                curr_val -= 1
                for u, v in links_by_insway.get(curr_val, []):
                    uf.union(u, v)
                max_size = uf.get_max_component_size()
                max_size_by_val[curr_val] = max_size
            t = curr_val + 1
        else:
            edge_count_above = np.zeros(max_insway + 1, dtype=int)
            curr_above = 0
            for j in range(max_insway, -1, -1):
                edge_count_above[j] = curr_above
                curr_above += len(links_by_insway[j])
                
            critical_insway = max_insway
            for j in range(max_insway - 1, -1, -1):
                if edge_count_above[j] < N:
                    critical_insway -= 1
            t = critical_insway + 1
            
        # 6. Apply threshold and detect connected components
        uf_final = UnionFind(core_nodes)
        for val in range(t, max_insway + 1):
            for u, v in links_by_insway.get(val, []):
                uf_final.union(u, v)
                
        components = {}
        for u in core_nodes:
            root = uf_final.find(u)
            if root not in components:
                components[root] = []
            components[root].append(u)
            
        labels = np.full(N, -1)
        cluster_id = 0
        for root, members in components.items():
            if len(members) > 1:
                for member in members:
                    labels[member] = cluster_id
                cluster_id += 1
                
        self.core_nodes = core_nodes
        self.mutual_friends = mutual_friends
        self.insway_scores = insway_scores
        self.selected_threshold = t
        self.max_insway = max_insway
        return labels
