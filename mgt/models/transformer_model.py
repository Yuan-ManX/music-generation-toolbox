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

    def train(self, x_train, epochs, batch_size=4, stop_loss=0.1):
        self.model.train()
        start_time = time.time()
        for epoch in range(epochs):
            print(f"Training epoch {epoch + 1}.")

            new_list = x_train.copy()
            random.shuffle(new_list)

            print(f"Number of midis: {len(new_list)}")
            flat_list = [item for sublist in new_list for item in sublist]
            chunks = list(create_chunks(flat_list, chunk_size=self.max_sequence_length))
            batches = list(create_chunks(chunks, chunk_size=batch_size))
            print(f"Number of batches: {len(batches)}")

            epoch_losses = []
            for batch in batches:
                # when training, set return_loss equal to True
                batch = torch.tensor(batch).long().cuda()

                loss = self.model(batch, return_loss=True)
                loss.backward()

                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 0.5)
                self.optimizer.step()
                self.optimizer.zero_grad()

                loss_item = loss.item()
                epoch_losses.append(loss_item)
                print(f"Batch loss is {loss_item}.")

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