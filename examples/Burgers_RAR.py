from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import numpy as np
import tensorflow as tf

import deepxde as dde


def gen_testdata():
    data = np.load("dataset/Burgers.npz")
    t, x, exact = data["t"], data["x"], data["usol"].T
    xx, tt = np.meshgrid(x, t)
    X = np.vstack((np.ravel(xx), np.ravel(tt))).T
    y = exact.flatten()[:, None]
    return X, y


def main():
    def pde(x, y):
        dy_x = tf.gradients(y, x)[0]
        dy_x, dy_t = dy_x[:, 0:1], dy_x[:, 1:2]
        dy_xx = tf.gradients(dy_x, x)[0][:, 0:1]
        return dy_t + y * dy_x - 0.01 / np.pi * dy_xx

    geom = dde.geometry.Interval(-1, 1)
    timedomain = dde.geometry.TimeDomain(0, 0.99)
    geomtime = dde.geometry.GeometryXTime(geom, timedomain)

    bc = dde.DirichletBC(
        geomtime, lambda x: np.zeros((len(x), 1)), lambda _, on_boundary: on_boundary
    )
    ic = dde.IC(
        geomtime, lambda x: -np.sin(np.pi * x[:, 0:1]), lambda _, on_initial: on_initial
    )

    data = dde.data.TimePDE(
        geomtime, pde, [bc, ic], num_domain=2500, num_boundary=100, num_initial=160
    )
    net = dde.maps.FNN([2] + [20] * 3 + [1], "tanh", "Glorot normal")
    model = dde.Model(data, net)

    model.compile("adam", lr=1.0e-3)
    model.train(epochs=10000)
    model.compile("L-BFGS-B")
    model.train()

    X = geomtime.random_points(100000)
    err = 1
    while err > 0.005:
        f = model.predict(X, operator=pde)
        err_eq = np.absolute(f)
        err = np.mean(err_eq)
        print("Mean residual: %.3e" % (err))

        x_id = np.argmax(err_eq)
        print("Adding new point:", X[x_id], "\n")
        data.add_anchors(X[x_id])
        early_stopping = dde.callbacks.EarlyStopping(min_delta=1e-4, patience=2000)
        model.compile("adam", lr=1e-3)
        model.train(
            epochs=10000, disregard_previous_best=True, callbacks=[early_stopping]
        )
        model.compile("L-BFGS-B")
        losshistory, train_state = model.train()
    dde.saveplot(losshistory, train_state, issave=True, isplot=True)

    X, y_true = gen_testdata()
    y_pred = model.predict(X)
    print("L2 relative error:", dde.metrics.l2_relative_error(y_true, y_pred))
    np.savetxt("test.dat", np.hstack((X, y_true, y_pred)))


if __name__ == "__main__":
    main()
