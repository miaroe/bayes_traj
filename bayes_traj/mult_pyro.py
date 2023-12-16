import torch
import pyro
import pyro.distributions as dist
from pyro.infer import SVI, TraceEnum_ELBO
from pyro.infer.autoguide import AutoNormal
from pyro.optim import ClippedAdam


class MultPyro:
    def __init__(
        self,
        *,  # force passing by keyword to avoid confusion
        w_mu0: torch.Tensor,
        w_var0: torch.Tensor,
        lambda_a0: torch.Tensor,
        lambda_b0: torch.Tensor,
        Y_sparse: torch.Tensor,  # [N, D], real value
        X_sparse: torch.Tensor,  # [N, M], real value
        sparse_individuals: torch.Tensor,  # [N] of value {0,...,G-1}
        K: int,  # TODO configured from say --num-components
    ) -> None:
        """
        See MultDPRegression for parameter descriptions.

        Attributes:
            K: number of components
            D: number of targets
            G: number of individuals
            M: number of predictors (aka features)
            N: number of observations
        """
        # Sizes.
        self.K = K
        self.D = D = Y_sparse.shape[1]
        self.M = M = X_sparse.shape[1]
        self.G = G = 1 + sparse_individuals.max().item()
        self.N = N = sparse_individuals.shape[0]
        assert K > 0
        assert D > 0
        assert M > 0
        assert G > 0

        # Validate shapes.
        assert w_mu0.shape == (D, M)
        assert w_var0.shape == (D, M)
        assert lambda_a0.shape == (D,)
        assert lambda_b0.shape == (D,)
        assert Y_sparse.shape == (N, D)
        assert X_sparse.shape == (N, M)
        assert sparse_individuals.shape == (N,)

        # Fixed parameters.
        self.w_mu0 = w_mu0
        self.w_var0 = w_var0
        self.lambda_a0 = lambda_a0
        self.lambda_b0 = lambda_b0

        # Data.
        self.Y_sparse = Y_sparse
        self.X_sparse = X_sparse
        self.sparse_individuals = sparse_individuals

        # Learned parameters.
        # self.R_ = R_
        # self.w_mu_ = w_mu_
        # self.w_var_ = w_var_
        # self.lambda_a = lambda_a
        # self.lambda_b = lambda_b

    def model(self) -> None:
        """
        The Bayesian model definition.

        This is called during training each SVI step, and during prediction.
        """
        D = self.D
        M = self.M
        K = self.K
        G = self.G
        N = self.N
        # We use three different dimensions for plates, which determines
        # max_plate_nesting.
        # See https://pyro.ai/examples/tensor_shapes.html
        components_plate = pyro.plate("components", K, dim=-3)
        targets_plate = pyro.plate("targets", D, dim=-2)
        individuals_plate = pyro.plate("individuals", G, dim=-1)
        predictors_plate = pyro.plate("predictors", M, dim=-1)
        observations_plate = pyro.plate("observations", N, dim=-1)

        with components_plate, targets_plate:
            # Variance parameters.
            lambda_ = pyro.sample(
                "lambda_", dist.Gamma(self.lambda_a0, self.lambda_b0)
            )
            assert lambda_.shape == (K, D, 1)

            # Sample the regression coefficients.
            with predictors_plate:
                # Each W_[k,d] is a vector over M, hence we unsqueeze.
                loc = self.w_mu0[..., None]
                scale = self.w_var0.sqrt[..., None]
                W_ = pyro.sample("W_", dist.Normal(loc, scale))
                assert W_.shape == (K, D, M)

        # Sample the mixture component of each individual.
        # This will be enumerated out during SVI.
        # See https://pyro.ai/examples/enumeration.html
        with individuals_plate:
            class_probs = torch.ones(K) / K
            class_g = pyro.sample("class_g", dist.Categorical(class_probs))
            assert class_g.shape in {
                (G,),  # During prediction.
                (K, 1, 1, G,),  # During training due to enumeration.
            }

        # Reshape from G to N.  This operation is valid because
        # observations_plate refines individuals_plate.
        class_n = class_g[..., self.sparse_individuals]
        assert class_n.shape in {
            (N,),  # During prediction.
            (K, 1, 1, N,),  # During training due to enumeration.
        }

        # Declare the likelihood.
        with observations_plate:
            # Compute predicted mean.
            W_n = W_[class_n]
            y_loc = (W_n * self.X_sparse[..., None]).sum(-1)
            y_scale = lambda_.sqrt()[class_n]
            # Observers Y_sparse.
            pyro.sample(
                "Y_sparse", dist.Normal(y_loc, y_scale), obs=self.Y_sparse
            )

    def fit(
        self,
        *,
        learning_rate: float = 0.01,
        learning_rate_decay: float = 0.1,
        num_steps: int = 1001,
        seed: int = 20231215,
    ) -> None:
        """Fits the model via SVI."""
        # Reset state to ensure reproducibility.
        pyro.clear_param_store()
        pyro.set_rng_seed(seed)

        # Run SVI.
        self.guide = guide = AutoNormal(self.model)
        optim = ClippedAdam(
            {"lr": learning_rate, "lrd": learning_rate_decay**(1 / num_steps)}
        )
        elbo = TraceEnum_ELBO(max_plate_nesting=3)
        svi = SVI(self.model, guide, optim, elbo)

        for step in range(num_steps):
            loss = svi.step()
            loss /= self.N  # Per-observation loss is more interpretable.
            if step % 100 == 0:
                print(f"step {step: >4d} loss = {loss:.3f}")

    def predict(
        self,
        X_sparse: torch.Tensor,
        individuals: torch.Tensor,
    ) -> torch.Tensor:
        """Predicts `Y_sparse` from `X_sparse`."""
        raise NotImplementedError

    def classify(
        self,
        X_sparse: torch.Tensor,
        individuals: torch.Tensor,
    ) -> torch.Tensor:
        """
        Classifies `X_sparse`.

        Returns:
            probs: A `[G, K]`-shaped tensor of probabilities, normalized over
                the leftmost dimension.
        """
        raise NotImplementedError
