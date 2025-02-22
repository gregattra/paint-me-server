import numpy as np
import tensorflow as tf
from image_functions import plot_images, plot_image_big, save_image, load_image

import vgg16

vgg16.maybe_download()

def mean_squared_error(a, b):
    return tf.reduce_mean(tf.square(a - b))

def create_content_loss(sess, model, content_image, layer_ids):
    feed_dict = model.create_feed_dict(image=content_image)
    layers = model.get_layer_tensors(layer_ids)
    values = sess.run(layers, feed_dict=feed_dict)
    with model.graph.as_default():
        layer_losses = []
        for value, layer in zip(values, layers):
            value_const = tf.constant(value)
            loss = mean_squared_error(layer, value)
            layer_losses.append(loss)
        total_loss = tf.reduce_mean(layer_losses)

    return total_loss

def gram_matrix(tensor):
    shape = tensor.get_shape()
    num_channels = int(shape[3])
    matrix = tf.reshape(tensor, shape=[-1, num_channels])
    gram = tf.matmul(tf.transpose(matrix), matrix)

    return gram

def create_style_loss(sess, model, style_image, layer_ids):
    feed_dict = model.create_feed_dict(image=style_image)
    layers = model.get_layer_tensors(layer_ids)
    with model.graph.as_default():
        gram_layers = [gram_matrix(layer) for layer in layers]
        values = sess.run(gram_layers, feed_dict=feed_dict)
        layer_losses = []
        for value, gram_layer in zip(values, gram_layers):
            value_const = tf.constant(value)
            loss = mean_squared_error(gram_layer, value_const)
            layer_losses.append(loss)

        total_loss = tf.reduce_mean(layer_losses)

    return total_loss

def create_denoise_loss(model):
    loss = tf.reduce_sum(tf.abs(model.input[:, 1:, :, :] - model.input[:, :-1, :, :])) + \
           tf.reduce_sum(tf.abs(model.input[:, :, 1:, :] - model.input[:, :, :-1, :]))

    return loss

def style_transfer( content_image, style_image,
                    content_layer_ids, style_layer_ids,
                    weight_content=1.5, weight_style=10.0,
                    weight_denoise=0.3, num_iterations=120, step_size=10.0):

    model = vgg16.VGG16()
    sess = tf.InteractiveSession(graph=model.graph)
    loss_content = create_content_loss(sess, model, content_image, content_layer_ids)
    loss_style = create_style_loss(sess, model, style_image, style_layer_ids)
    loss_denoise = create_denoise_loss(model)

    adj_content = tf.Variable(1e-10, name='adj_content')
    adj_style = tf.Variable(1e-10, name='adj_style')
    adj_denoise = tf.Variable(1e-10, name='adj_denoise')
    sess.run([adj_content.initializer,
              adj_style.initializer,
              adj_denoise.initializer])

    update_adj_content = adj_content.assign(1.0 / (loss_content + 1e-10))
    update_adj_style = adj_style.assign(1.0 / (loss_style + 1e-10))
    update_adj_denoise = adj_denoise.assign(1.0 / (loss_denoise + 1e-10))

    loss_combined = weight_content * adj_content * loss_content + \
                    weight_style * adj_style * loss_style + \
                    weight_denoise * adj_denoise * loss_denoise

    gradient = tf.gradients(loss_combined, model.input)

    run_list = [gradient, update_adj_content, update_adj_style, update_adj_denoise]

    mixed_image = np.random.rand(*content_image.shape) + 128

    for i in range(num_iterations):
        feed_dict = model.create_feed_dict(image=mixed_image)
        grad, adj_content_val, adj_style_val, adj_denoise_val = sess.run(run_list, feed_dict)
        grad = np.squeeze(grad)
        step_size_scaled = step_size / (np.std(grad) + 1e-8)
        mixed_image -= grad * step_size_scaled  # step_size = alpha / learning rate
        mixed_image = np.clip(mixed_image, 0.0, 255.0)
        print('.', end='')
        if (i % 10 == 0) or (i == num_iterations - 1):
            print('Iteration:', i)
            msg = 'Weight Adj. for Content: {0:.2e}, Style: {1:.2e}, Denoise: {1:.2e}'
            print(msg.format(adj_content_val, adj_style_val, adj_denoise_val))
            # plot_images(content_image, style_image, mixed_image)

    print('Final image:')
    plot_image_big(mixed_image)

    sess.close()

    return mixed_image


content_filename = 'images/content_image.jpg'
content_image = load_image(content_filename)

style_filename = 'images/style_image.jpg'
style_image = load_image(style_filename)

content_layer_ids = [6]
style_layer_ids =  list(range(13))

image = style_transfer(content_image=content_image, style_image=style_image,
                       content_layer_ids=content_layer_ids, style_layer_ids=style_layer_ids,
                       weight_content=1.5, weight_style=10.0, weight_denoise=0.3,
                       num_iterations=60, step_size=10.0)

# save_image(image, 'images/milo_3.jpg')
