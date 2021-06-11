from datetime import time

import random
import time

import torch
import numpy as np

from x_transformers import TransformerWrapper, Decoder, AutoregressiveWrapper

from mgt.datamanagers.data_manager import Dictionary


def create_chunks(iterable, chunk_size=1):
    array_length = len(iterable)
    for ndx in range(0, array_length, chunk_size):
        yield iterable[ndx:min(ndx + chunk_size, array_length)]


def create_sequences(training_data, max_sequence_length, padding_character=0):
    sequences = []
    for song in training_data:
        padded_song = list(np.repeat([padding_character], max_sequence_length)) + song
        for i in range(len(padded_song) - max_sequence_length):
            sequence = padded_song[i: i + max_sequence_length]
            sequences.append(sequence)
    return sequences


class TransformerModel(object):

    def __init__(self,
                 dictionary: Dictionary,
                 max_sequence_length=512,
                 learning_rate=2e-4,
                 dropout=0.1,
                 dim=512,
                 depth=6,
                 heads=8
                 ):
        self.dictionary = dictionary
        self.learning_rate = learning_rate
        self.max_sequence_length = max_sequence_length
        self.model = self.create_model(
            num_tokens=dictionary.size(),
            max_seq_len=max_sequence_length,
            dropout=dropout,
            dim=dim,
            depth=depth,
            heads=heads
        )
        self.optimizer = self.create_optimizer()

    def train(self, x_train, epochs, batch_size=8, stop_loss=0.1, report_per_x_batches=25):
        self.model.train()
        start_time = time.time()
        for epoch in range(epochs):
            print(f"Training epoch {epoch + 1}.")

            sequences = create_sequences(x_train, self.max_sequence_length)
            random.shuffle(sequences)
            batches = list(create_chunks(sequences, chunk_size=batch_size))
            print(f"Number of batches: {len(batches)}")

            epoch_losses = []
            batch_losses = []
            nr_of_batches_processed = 0
            for batch in batches:
                # when training, set return_loss equal to True
                batch = torch.tensor(batch).long().cuda()

                loss = self.model(batch)
                loss.backward()

                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 0.5)
                self.optimizer.step()
                self.optimizer.zero_grad()

                nr_of_batches_processed += 1

                loss_item = loss.item()

                batch_losses.append(loss_item)
                epoch_losses.append(loss_item)

                if nr_of_batches_processed % report_per_x_batches == 0:
                    print(f"Processed {nr_of_batches_processed} / {len(batches)} with loss {np.mean(batch_losses)}.")
                    batch_losses = []

            epoch_loss = np.mean(epoch_losses)
            if epoch_loss <= stop_loss:
                print(f"Loss of {epoch_loss} was lower than stop loss of {stop_loss}. Stopping training.")
                return

            running_time = (time.time() - start_time)
            print(f"Loss after epoch {epoch + 1} is {epoch_loss}. Running time: {running_time}")

    def generate(self, output_length=100):
        self.model.eval()
        initial = torch.tensor([[0]]).long().cuda()  # assume 0 is start token

        sample = self.model.generate(initial, output_length, temperature=1., filter_thres=0.9)
        return sample.cpu().detach().numpy()[0]

    def create_model(self, num_tokens, max_seq_len, dropout, dim, depth, heads):
        model = AutoregressiveWrapper(TransformerWrapper(
            num_tokens=num_tokens,
            max_seq_len=max_seq_len,
            emb_dropout=dropout,  # dropout after embedding
            attn_layers=Decoder(
                dim=dim,
                depth=depth,
                heads=heads,
                attn_dropout=dropout,  # dropout post-attention
                ff_dropout=dropout  # feedforward dropout
            )
        )).cuda()

        return model

    def create_optimizer(self):
        return torch.optim.Adam(self.model.parameters(), lr=self.learning_rate)

    def save_model(self, path):
        checkpoint = {'state_dict': self.model.state_dict(), 'optimizer': self.optimizer.state_dict()}
        if path.endswith("_sd_opt.pth"):
            torch.save(checkpoint, path + "_sd_opt.pth")
        else:
            torch.save(checkpoint, path + "_sd_opt.pth")

    def load_model(self, path):
        if path.endswith("_sd_opt.pth"):
            torch.load(path)
        else:
            torch.load(path + "_sd_opt.pth")
        self.model.eval()
