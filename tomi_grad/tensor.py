from collections.abc import Callable
import numpy as np
import numpy.typing as npt


class Var:
    def __init__(self, array: npt.ArrayLike, requires_grad=False, precision=np.float64):
        self.requires_grad = requires_grad
        self._grad: npt.ArrayLike | None = None
        self.pointers: list[tuple[Var, Callable]] = []

        # TODO: type check this
        self.precision = precision

        self.arr = np.array(array, dtype=precision)

        self.dim = self.arr.ndim
        self.shape = self.arr.shape

    @property
    def grad(self):
        return self._grad

    def zeroGrad(self):
        self._grad = np.zeros_like(self.arr)
        for var, _ in self.pointers:
            var.zeroGrad()

    def _backward(self, _value: np.ndarray | float = 1.0):
        if not self.requires_grad:
            return

        if self._grad is None:
            self._grad = np.zeros_like(_value)
        _value = np.array(_value, dtype=self.precision)

        self._grad += _value
        for _var, _local_grad in self.pointers:
            if _var.requires_grad:
                _var._backward(_local_grad(_value))

    def backprop(self):
        self._backward()

    def sum(self):
        result_value = np.sum(self.arr)
        result = Var(result_value, requires_grad=self.requires_grad)

        if self.requires_grad:

            def _grad_sum(_value):
                return _value * np.ones_like(self.arr)

            result.pointers.append((self, _grad_sum))

        return result

    def sqrt(self):
        return vSqrt(self)

    @property
    def T(self):
        return vTranspose(self)

    def _forward(self):
        raise NotImplementedError

    def get_operation(self):
        raise NotImplementedError

    def get_consumers(self):
        raise NotImplementedError

    def get_inputs(self):
        raise NotImplementedError

    def __add__(self, other):
        other = _to_var(other)
        return vAdd(self, other)

    def __radd__(self, other):
        other = _to_var(other)
        return vAdd(other, self)

    def __sub__(self, other):
        other = _to_var(other)
        return vAdd(self, -1.0 * other)

    def __rsub__(self, other):
        other = _to_var(other)
        return vAdd(other, -1.0 * self)

    def __mul__(self, other):
        other = _to_var(other)
        return vMul(self, other)

    def __rmul__(self, other):
        other = _to_var(other)
        return vMul(other, self)

    def __truediv__(self, b):
        return vMul(self, pow(b, -1.0))

    def __rtruediv__(self, b):
        return vMul(b, pow(self, -1))

    def __pow__(self, other):
        other = _to_var(other)
        return vPow(self, other)

    def __matmul__(self, other):
        other = _to_var(other)
        return vMatMul(self, other)

    def __neg__(self):
        return -1 * self

    def __str__(self):
        return str(self.arr)

    def __repr__(self):
        return str(self.arr)


def _to_var(x):
    if isinstance(x, Var):
        x.arr = np.array(x.arr)
        return x
    else:
        x_var = Var(x)
        x_var.arr = np.array(x_var.arr)
        return x_var


def vSqrt(A: Var):
    A = _to_var(A)
    result = Var(np.sqrt(A.arr))
    result.requires_grad = A.requires_grad

    if A.requires_grad:

        def _grad_sqrt(_value):
            return _value * (0.5 / np.sqrt(A.arr))

        result.pointers.append((A, _grad_sqrt))
    return result


def vTranspose(A: Var):
    A = _to_var(A)
    result = Var(A.arr.T, requires_grad=A.requires_grad)
    if A.requires_grad:

        def _grad_t(_value):
            return _value.T

        result.pointers.append((A, _grad_t))
    return result


# PASSED
def vMatMul(A: Var, B: Var):
    A = _to_var(A)
    B = _to_var(B)

    result = np.matmul(A.arr, B.arr)
    required_grad = A.requires_grad or B.requires_grad
    result = Var(result, requires_grad=required_grad)

    if A.requires_grad:

        def _grad_a(_value):
            return np.matmul(_value, B.arr.T)  # G @ B.T

        result.pointers.append((A, _grad_a))

    if B.requires_grad:

        def _grad_b(_value):
            return np.matmul(A.arr.T, _value)  # A.T @ G

        result.pointers.append((B, _grad_b))

    return result


def vAdd(A: Var | float | int, B: Var | float | int):
    A = _to_var(A)
    B = _to_var(B)

    result = Var(A.arr + B.arr, requires_grad=(A.requires_grad or B.requires_grad))

    if A.requires_grad:

        def _grad_a(_value):
            sum_axes = []
            for i in range(len(_value.shape)):
                if i < len(A.shape):
                    if A.shape[i] == 1 and _value.shape[i] > 1:
                        sum_axes.append(i)
                else:
                    sum_axes.append(i)

            return np.sum(_value, axis=tuple(sum_axes), keepdims=True)

        result.pointers.append((A, _grad_a))
    if B.requires_grad:

        def _grad_b(_value):
            sum_axes = []
            for i in range(len(_value.shape)):
                if i < len(B.shape):
                    if B.shape[i] == 1 and _value.shape[i] > 1:
                        sum_axes.append(i)
                else:
                    sum_axes.append(i)
            return np.sum(_value, axis=tuple(sum_axes), keepdims=True)

        result.pointers.append((B, _grad_b))

    return result


def vMul(A: Var, B: Var):
    A = _to_var(A)
    B = _to_var(B)

    result = Var(A.arr * B.arr, requires_grad=(A.requires_grad or B.requires_grad))

    if A.requires_grad:

        def _grad_a(incoming_grad):
            sum_axes = []
            for i in range(len(incoming_grad.shape)):
                if i < len(A.shape):
                    if A.shape[i] == 1 and incoming_grad.shape[i] > 1:
                        sum_axes.append(i)
                else:
                    sum_axes.append(i)
            return np.sum(incoming_grad * B.arr, axis=tuple(sum_axes), keepdims=True)

        result.pointers.append((A, _grad_a))

    if B.requires_grad:

        def _grad_b(incoming_grad):
            sum_axes = []
            for i in range(len(incoming_grad.shape)):
                if i < len(B.shape):
                    if B.shape[i] == 1 and incoming_grad.shape[i] > 1:
                        sum_axes.append(i)
                else:
                    sum_axes.append(i)
            return np.sum(incoming_grad * A.arr, axis=tuple(sum_axes), keepdims=True)

        result.pointers.append((B, _grad_b))

    return result


def vPow(A: Var, exponent: Var):
    A = _to_var(A)
    _exponent = _to_var(exponent)

    _array = np.array(A.arr)
    _exponent = np.array(exponent.arr)
    result = Var(
        np.power(_array, _exponent),
        requires_grad=(A.requires_grad or exponent.requires_grad),
    )

    if A.requires_grad:

        def _grad_a(_value):
            local_grad = exponent.arr * np.power(A.arr, exponent.arr - 1)

            # Handle broadcasting.
            sum_axes = []
            for i in range(len(_value.shape)):
                if i < len(A.shape):
                    if A.shape[i] == 1 and _value.shape[i] > 1:
                        sum_axes.append(i)
                else:
                    sum_axes.append(i)
            return np.sum(_value * local_grad, axis=tuple(sum_axes), keepdims=True)
        result.pointers.append((A, _grad_a))

    if exponent.requires_grad:

        def _grad_exponent(_value):
            local_grad = np.power(A.arr, _exponent) * np.log(A.arr)

            sum_axes = []
            for i in range(len(_value.shape)):
                if i < len(_exponent.shape):
                    if exponent.shape[i] == 1 and _value.shape[i] > 1:
                        sum_axes.append(i)
                else:
                    sum_axes.append(i)
            return np.sum(
                _value * local_grad, axis=tuple(sum_axes), keepdims=True
            )

        result.pointers.append((exponent, _grad_exponent))

    return result
